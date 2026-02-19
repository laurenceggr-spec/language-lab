import streamlit as st
import pandas as pd
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Language Lab FWB", page_icon="🇧🇪", layout="wide")

# Sécurisation de la clé : On vérifie les deux sources possibles
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    # Backup au cas où tu l'as mise ailleurs, mais les Secrets sont prioritaires
    api_key = st.sidebar.text_input("Clé API OpenAI non configurée :", type="password")

if not api_key:
    st.error("⚠️ Clé API manquante. Configurez-la dans les 'Secrets' de Streamlit.")
    st.stop()

client = openai.OpenAI(api_key=api_key)

# Configuration Sheets FWB
SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- 2. SESSION STATE ---
if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": st.query_params.get("l", "Anglais"),
        "niveau": st.query_params.get("n", "A2"),
        "grammaire": st.query_params.get("g", "Général"),
        "mode": "Interaction (Dialogue)",
        "consigne_eleve": st.query_params.get("c", "Présente-toi au tuteur."),
        "role_ia": "Tu es un tuteur de langue bienveillant pour le Tronc Commun (FWB)."
    }

# --- 3. ACCÈS ---
def verifier_licence(cle):
    try:
        df = pd.read_csv(SHEET_URL)
        df['cle_licence'] = df['cle_licence'].astype(str).str.strip()
        res = df[df['cle_licence'] == str(cle).strip()]
        return res.iloc[0]['nom_client'] if not res.empty else None
    except: return None

if st.session_state.role is None:
    st.title("🎙️ Language Lab")
    t1, t2 = st.tabs(["👨‍🏫 Professeur", "🎓 Élève"])
    with t1:
        cle_input = st.text_input("Clé école :", type="password")
        if st.button("Connexion Prof"):
            nom = verifier_licence(cle_input)
            if nom: st.session_state.role = "Professeur"; st.session_state.nom_abonne = nom; st.rerun()
    with t2:
        nom_e = st.text_input("Prénom élève :")
        if st.button("Commencer"):
            if nom_e: st.session_state.nom_eleve = nom_e; st.session_state.role = "Eleve"; st.rerun()

# --- 4. DASHBOARD PROFESSEUR ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.nom_abonne}")
    t_reg, t_cons, t_qr = st.tabs(["🎯 Réglages", "📝 Scénario", "📲 Partage"])
    
    with t_reg:
        st.session_state.config["langue"] = st.selectbox("Langue :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"], index=0)
        st.session_state.config["niveau"] = st.select_slider("Niveau :", ["A1", "A2", "B1", "B2"], value=st.session_state.config["niveau"])
        st.session_state.config["role_ia"] = st.text_area("Rôle IA :", value=st.session_state.config["role_ia"])
        st.session_state.config["grammaire"] = st.text_input("Grammaire :", value=st.session_state.config["grammaire"])

    with t_cons:
        st.session_state.config["consigne_eleve"] = st.text_area("Consigne élève :", value=st.session_state.config["consigne_eleve"])

    with t_qr:
        p = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "g": st.session_state.config["grammaire"], "c": st.session_state.config["consigne_eleve"]}
        link = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(p)
        st.image(qrcode.make(link).get_image(), width=150)

    if st.sidebar.button("🚀 Mode Élève"): st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"): st.session_state.role = None; st.rerun()

# --- 5. INTERFACE ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Hello {st.session_state.get('nom_eleve')} !")
    st.info(f"📋 **Mission :** {st.session_state.config['consigne_eleve']}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    audio_file = st.audio_input("Parle maintenant...")

    if audio_file:
        with st.spinner("Analyse..."):
            # Transcription Whisper
            trans = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_file))
            st.session_state.messages.append({"role": "user", "content": trans.text})
            
            # Réponse GPT (On force le scénario du prof ici)
            prompt = f"{st.session_state.config['role_ia']}. Scénario: {st.session_state.config['consigne_eleve']}. Langue: {st.session_state.config['langue']}. Niveau: {st.session_state.config['niveau']}."
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}] + st.session_state.messages
            )
            txt_ia = resp.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": txt_ia})
            
            # Synthèse Vocale immédiate
            audio_ia = client.audio.speech.create(model="tts-1", voice="alloy", input=txt_ia, response_format="mp3")
            st.session_state.last_audio = audio_ia.content
            st.rerun()

    if "last_audio" in st.session_state and st.session_state.last_audio:
        st.audio(st.session_state.last_audio, format="audio/mpeg", autoplay=True)
        # On garde le message pour l'affichage mais on vide le son pour ne pas boucler
        st.session_state.last_audio = None

    with st.sidebar:
        if st.button("📊 Bilan final"):
            bilan = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "Bilan FWB (Aisance, Richesse, Intelligibilité)."}] + st.session_state.messages)
            st.info(bilan.choices[0].message.content)
            st.download_button("📥 Télécharger", data=bilan.choices[0].message.content, file_name="bilan.txt")
        if st.button("⬅️ Quitter"):
            st.session_state.messages = []; st.session_state.role = None; st.rerun()
