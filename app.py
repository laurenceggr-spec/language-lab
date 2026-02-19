import streamlit as st
import pandas as pd
import openai
import qrcode
from io import BytesIO

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🎙️", layout="wide")

SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Connexion via Secrets
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Initialisation
if "role" not in st.session_state: st.session_state.role = None
if "nom_eleve" not in st.session_state: st.session_state.nom_eleve = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "last_audio" not in st.session_state: st.session_state.last_audio = None
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": "Anglais",
        "niveau": "A2",
        "grammaire": "Général",
        "mode": "Interaction (Dialogue)",
        "role_ia": "Tu es un tuteur de langue bienveillant."
    }

# --- 2. ACCÈS ---
if st.session_state.role is None:
    st.title("🎙️ Language Lab")
    tab1, tab2 = st.tabs(["👨‍🏫 Professeur", "🎓 Élève"])
    with tab1:
        cle = st.text_input("Clé d'activation :", type="password")
        if st.button("Connexion"):
            st.session_state.role = "Professeur"; st.rerun()
    with tab2:
        nom = st.text_input("Ton prénom :")
        if st.button("Commencer"):
            st.session_state.nom_eleve = nom; st.session_state.role = "Eleve"; st.rerun()

# --- 3. DASHBOARD PROFESSEUR ---
elif st.session_state.role == "Professeur":
    st.title("👨‍🏫 Configuration")
    st.session_state.config["langue"] = st.selectbox("Langue :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"])
    st.session_state.config["niveau"] = st.select_slider("Niveau :", ["A1", "A2", "B1", "B2"])
    st.session_state.config["role_ia"] = st.text_area("Consigne :", value=st.session_state.config["role_ia"])
    if st.button("Sortir"): st.session_state.role = None; st.rerun()

# --- 4. INTERFACE ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Hello {st.session_state.nom_eleve} !")
    
    # Zone de Chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Entrée Audio (clé unique pour éviter la répétition)
    audio_value = st.audio_input("Parle ici", key="microphone")

    if audio_value and (st.session_state.get("last_processed_audio") != audio_value.id):
        with st.spinner("L'IA répond..."):
            # 1. Transcription
            transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_value))
            texte_eleve = transcript.text
            st.session_state.messages.append({"role": "user", "content": texte_eleve})
            
            # 2. Réponse IA
            prompt_ia = f"{st.session_state.config['role_ia']}. Réponds en {st.session_state.config['langue']}."
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt_ia}] + 
                         [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            )
            reponse_ia = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
            
            # 3. Génération Son
            audio_gen = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia)
            st.session_state.last_audio = audio_gen.content
            st.session_state.last_processed_audio = audio_value.id # Empêche la boucle infinie
            st.rerun()

    # Lecture du son (une seule fois après la réponse)
    if st.session_state.last_audio:
        st.audio(st.session_state.last_audio, format="audio/mp3", autoplay=True)
        st.session_state.last_audio = None # Efface le son après lecture pour éviter qu'il rejoue au prochain clic

    if st.sidebar.button("Quitter"):
        st.session_state.messages = []; st.session_state.role = None; st.rerun()
