import streamlit as st
import pandas as pd
import openai
import qrcode
from io import BytesIO

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🎙️", layout="wide")

# Connexion aux ressources
SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Initialisation des variables de session
if "role" not in st.session_state: st.session_state.role = None
if "nom_eleve" not in st.session_state: st.session_state.nom_eleve = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "last_audio" not in st.session_state: st.session_state.last_audio = None
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": "Anglais",
        "niveau": "A2",
        "grammaire": "Général (Présent/Passé)",
        "mode": "Interaction (Dialogue)",
        "role_ia": "Tu es un tuteur de langue bienveillant pour des élèves belges du tronc commun."
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
    st.caption("Fédération Wallonie-Bruxelles - Portail Pédagogique")
    tab1, tab2 = st.tabs(["👨‍🏫 Espace Enseignant", "🎓 Espace Élève"])
    
    with tab1:
        cle = st.text_input("Clé d'activation école :", type="password")
        if st.button("Connexion Enseignant"):
            nom = verifier_licence(cle)
            if nom:
                st.session_state.role = "Professeur"
                st.session_state.nom_abonne = nom
                st.rerun()
            else: st.error("Clé invalide.")
            
    with tab2:
        nom_saisi = st.text_input("Entre ton prénom :")
        if st.button("Commencer l'exercice"):
            if nom_saisi:
                st.session_state.nom_eleve = nom_saisi
                st.session_state.role = "Eleve"
                st.rerun()
            else: st.warning("Veuillez entrer un prénom.")

# --- 4. DASHBOARD PROFESSEUR (RESTAURÉ) ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.nom_abonne}")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🎯 Réglages Pédagogiques")
        st.session_state.config["langue"] = st.selectbox("Langue :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"])
        st.session_state.config["niveau"] = st.select_slider("Niveau Tronc Commun :", ["A1", "A2", "B1", "B2"])
        st.session_state.config["grammaire"] = st.text_input("Focus Grammatical :", value=st.session_state.config["grammaire"])
        st.session_state.config["mode"] = st.radio("Mode d'exercice :", ["Interaction (Dialogue)", "Production continue"])

    with col_b:
        st.subheader("🤖 Personnalisation de l'IA")
        st.session_state.config["role_ia"] = st.text_area("Consigne spécifique pour l'IA :", value=st.session_state.config["role_ia"])
        
        st.divider()
        st.subheader("📲 Partage")
        url_app = "https://language-lab.streamlit.app"
        qr = qrcode.make(url_app); buf = BytesIO(); qr.save(buf)
        st.image(buf, width=150, caption="QR Code pour la classe")

    st.sidebar.divider()
    if st.sidebar.button("🚀 Passer au mode Élève"): st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"): st.session_state.role = None; st.rerun()

# --- 5. INTERFACE ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Hello {st.session_state.nom_eleve} !")
    st.info(f"Langue : {st.session_state.config['langue']} | Niveau : {st.session_state.config['niveau']} | Focus : {st.session_state.config['grammaire']}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Entrée Audio avec protection contre la boucle infinie
    audio_value = st.audio_input("Parle maintenant...", key="mic_eleve")

    if audio_value and (st.session_state.get("last_processed_audio") != audio_value.id):
        with st.spinner("J'écoute..."):
            transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_value))
            texte_eleve = transcript.text
            st.session_state.messages.append({"role": "user", "content": texte_eleve})
            
            prompt_ia = f"{st.session_state.config['role_ia']}. Niveau {st.session_state.config['niveau']}. Focus {st.session_state.config['grammaire']}. Réponds en {st.session_state.config['langue']}."
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt_ia}] + 
                         [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            )
            reponse_ia = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
            
            # Préparation du son
            audio_gen = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia)
            st.session_state.last_audio = audio_gen.content
            st.session_state.last_processed_audio = audio_value.id
            st.rerun()

    # Lecture du son
    if st.session_state.last_audio:
        st.audio(st.session_state.last_audio, format="audio/mp3", autoplay=True)
        st.session_state.last_audio = None

    with st.sidebar:
        if st.button("⬅️ Quitter"):
            st.session_state.messages = []; st.session_state.role = None; st.rerun()
