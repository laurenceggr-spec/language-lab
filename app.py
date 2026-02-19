import streamlit as st
import pandas as pd
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Language Lab", page_icon="🇧🇪", layout="wide")

# Configuration des accès
SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Utilisation des Secrets Streamlit pour la clé API (indispensable pour GitHub)
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Récupération des paramètres URL pour le QR Code
query_params = st.query_params

# Initialisation des variables de session
if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": query_params.get("l", "Anglais"),
        "niveau": query_params.get("n", "A2"),
        "grammaire": query_params.get("g", "Général"),
        "mode": "Interaction (Dialogue)",
        "consigne_eleve": query_params.get("c", "Présente-toi au tuteur."),
        "role_ia": "Tu es un tuteur de langue bienveillant."
    }

# --- 2. FONCTIONS ---
def verifier_licence(cle_saisie):
    try:
        df = pd.read_csv(SHEET_URL)
        df['cle_licence'] = df['cle_licence'].astype(str).str.strip()
        client_data = df[df['cle_licence'] == str(cle_saisie).strip()]
        return client_data.iloc[0]['nom_client'] if not client_data.empty else None
    except: return None

# --- 3. ACCÈS ---
if st.session_state.role is None:
    st.title("🎙️ Language Lab")
    tab_p, tab_e = st.tabs(["👨‍🏫 Professeur", "🎓 Élève"])
    
    with tab_p:
        cle = st.text_input("Clé d'activation école :", type="password")
        if st.button("Connexion"):
            nom = verifier_licence(cle)
            if nom:
                st.session_state.role = "Professeur"
                st.session_state.nom_abonne = nom
                st.rerun()
            else: st.error("Clé invalide.")
            
    with tab_e:
        nom_e = st.text_input("Entre ton prénom :")
        if st.button("Commencer l'exercice"):
            if nom_e:
                st.session_state.nom_eleve = nom_e
                st.session_state.role = "Eleve"
                st.rerun()

# --- 4. DASHBOARD PROFESSEUR ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Configuration - {st.session_state.nom_abonne}")
    
    t_reg, t_cons, t_qr = st.tabs(["🎯 Réglages", "📝 Consignes Élève", "📲 Partage"])
    
    with t_reg:
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.config["langue"] = st.selectbox("Langue :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"], index=["Anglais", "Néerlandais", "Allemand", "Espagnol"].index(st.session_state.config["langue"]))
            st.session_state.config["niveau"] = st.select_slider("Niveau CEFR :", ["A1", "A2", "B1", "B2", "C1"], value=st.session_state.config["niveau"])
        with col2:
            st.session_state.config["grammaire"] = st.text_input("Focus grammatical :", value=st.session_state.config["grammaire"])
            st.session_state.config["mode"] = st.radio("Mode :", ["Interaction (Dialogue)", "Production continue"], index=0 if st.session_state.config["mode"] == "Interaction (Dialogue)" else 1)
        st.session_state.config["role_ia"] = st.text_area("Rôle de l'IA (caché) :", value=st.session_state.config["role_ia"])

    with t_cons:
        st.session_state.config["consigne_eleve"] = st.text_area("Instructions affichées à l'élève :", value=st.session_state.config["consigne_eleve"])

    with t_qr:
        # Création du lien dynamique pour le QR Code
        base_url = "https://language-lab.streamlit.app/?"
        params = {
            "l": st.session_state.config["langue"],
            "n": st.session_state.config["niveau"],
            "g": st.session_state.config["grammaire"],
            "c": st.session_state.config["consigne_eleve"]
        }
        full_url = base_url + urllib.parse.urlencode(params)
        qr = qrcode.make(full_url); buf = BytesIO(); qr.save(buf)
        st.image(buf, width=150, caption="Scan pour synchroniser")
        st.info("Le QR Code contient vos réglages actuels.")

    if st.sidebar.button("🚀 Lancer la session Élève"):
        st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.role = None; st.rerun()

# --- 5. INTERFACE ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Hello {st.session_state.get('nom_eleve', 'élève')} !")
    
    with st.expander("📖 Tes consignes", expanded=True):
        st.write(f"**Objectif :** {st.session_state.config['consigne_eleve']}")
        st.caption(f"{st.session_state.config['langue']} | {st.session_state.config['niveau']} | {st.session_state.config['grammaire']}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    audio_value = st.audio_input("Parle maintenant...")

    if audio_value:
        with st.spinner("Analyse..."):
            audio_data = audio_value.read()
            transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_data))
            texte_eleve = transcript.text
            st.session_state.messages.append({"role": "user", "content": texte_eleve})
            
            if st.session_state.config["mode"] == "Interaction (Dialogue)":
                sys_prompt = f"{st.session_state.config['role_ia']}. Langue: {st.session_state.config['langue']}. Niveau: {st.session_state.config['niveau']}."
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages
                )
                reponse_ia = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
                
                # Relance l'affichage pour voir le nouveau message
                st.rerun()

    # Lecture audio automatique de la dernière réponse IA
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        last_msg = st.session_state.messages[-1]["content"]
        audio_res = client.audio.speech.create(model="tts-1", voice="alloy", input=last_msg)
        st.audio(audio_res.content, format="audio/mp3", autoplay=True)

    with st.sidebar:
        if st.button("📊 Bilan final"):
            bilan = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "Fais un bilan court des erreurs et progrès."}] + st.session_state.messages
            )
            st.write(bilan.choices[0].message.content)
        if st.button("⬅️ Retour"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.rerun()
