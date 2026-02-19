import streamlit as st
import pandas as pd
import openai
import qrcode
from io import BytesIO
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Language Lab", page_icon="🇧🇪", layout="wide")

# /!\ À REMPLIR
SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8/export?format=csv"
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Initialisation des variables de session
if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": "Anglais",
        "niveau": "A2",
        "grammaire": "Général",
        "mode": "Interaction (Dialogue)",
        "role_ia": "Tu es un tuteur de langue bienveillant."
    }

# --- 2. FONCTIONS ---
def verifier_licence(cle_saisie):
    try:
        df = pd.read_csv(SHEET_URL)
        client_data = df[df['cle_licence'] == cle_saisie]
        return client_data.iloc[0]['nom_client'] if not client_data.empty else None
    except: return None

# --- 3. ACCÈS ---
if st.session_state.role is None:
    st.title("🎙️ Language Lab")
    cle = st.text_input("Clé d'activation école :", type="password")
    if st.button("Connexion"):
        nom = verifier_licence(cle)
        if nom:
            st.session_state.role = "Professeur"
            st.session_state.nom_abonne = nom
            st.rerun()
        else: st.error("Clé invalide.")

# --- 4. DASHBOARD PROFESSEUR (OPTIONS COMPLÈTES) ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Configuration - {st.session_state.nom_abonne}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🎯 Objectifs Pédagogiques")
        st.session_state.config["langue"] = st.selectbox("Langue :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"])
        st.session_state.config["niveau"] = st.select_slider("Niveau CEFR :", ["A1", "A2", "B1", "B2", "C1"])
        st.session_state.config["grammaire"] = st.text_input("Attentes grammaticales spécifiques :", placeholder="Ex: Present Perfect, inversion, adjectifs...")
        st.session_state.config["mode"] = st.radio("Mode d'exercice :", ["Interaction (Dialogue)", "Production continue (L'élève parle seul)"])

    with col2:
        st.subheader("🤖 Personnalisation de l'IA")
        st.session_state.config["role_ia"] = st.text_area("Rôle de l'IA (Prompt) :", 
            value="Tu es un tuteur de langue. Aide l'élève à pratiquer son oral de manière ludique.")
        
        st.divider()
        st.write("📲 **Partage élève :**")
        url_app = "https://language-lab.streamlit.app" 
        qr = qrcode.make(url_app); buf = BytesIO(); qr.save(buf)
        st.image(buf, width=150)

    if st.sidebar.button("🚀 Lancer la session Élève"):
        st.session_state.role = "Eleve"
        st.rerun()

# --- 5. INTERFACE ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Language Lab : {st.session_state.config['langue']}")
    st.caption(f"Objectif : {st.session_state.config['niveau']} | Focus : {st.session_state.config['grammaire']}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    audio_value = st.audio_input("Parle maintenant...")

    if audio_value:
        with st.spinner("Analyse..."):
            audio_data = audio_value.read()
            transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_data))
            texte_eleve = transcript.text
        
        st.session_state.messages.append({"role": "user", "content": texte_eleve})
        with st.chat_message("user"): st.markdown(texte_eleve)

        # Si mode interaction, l'IA répond
        if st.session_state.config["mode"] == "Interaction (Dialogue)":
            with st.chat_message("assistant"):
                sys_prompt = f"""{st.session_state.config['role_ia']}. 
                Langue: {st.session_state.config['langue']}. Niveau: {st.session_state.config['niveau']}. 
                Surveille particulièrement: {st.session_state.config['grammaire']}."""
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages
                )
                reponse_ia = response.choices[0].message.content
                st.markdown(reponse_ia)
                audio_res = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia)
                st.audio(audio_res.content, format="audio/mp3", autoplay=True)
                st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
        else:
            st.success("Enregistré ! Continue de parler ou demande ton bilan.")

    # Barre latérale pour bilan et retour
    with st.sidebar:
        if st.button("📊 Voir mon bilan final"):
            st.subheader("Bilan Pédagogique")
            # Analyse basée sur les attentes du prof
            bilan = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": f"Évalue l'élève sur son niveau {st.session_state.config['niveau']} et sa grammaire ({st.session_state.config['grammaire']})."}] + st.session_state.messages
            )
            st.write(bilan.choices[0].message.content)
        
        if st.button("⬅️ Retour au Dashboard"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.rerun()
