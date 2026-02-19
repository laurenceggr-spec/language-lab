import streamlit as st
import pandas as pd
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🇧🇪", layout="wide")

SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

query_params = st.query_params

if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": query_params.get("l", "Anglais"),
        "niveau": query_params.get("n", "A2"),
        "grammaire": query_params.get("g", "Général"),
        "mode": "Interaction (Dialogue)",
        "consigne_eleve": query_params.get("c", "Présente-toi au tuteur."),
        "role_ia": "Tu es un tuteur de langue bienveillant pour le Tronc Commun (FWB). Focus sur l'UAA3."
    }

# --- 2. ACCÈS & LICENCE ---
def verifier_licence(cle_saisie):
    try:
        df = pd.read_csv(SHEET_URL)
        df['cle_licence'] = df['cle_licence'].astype(str).str.strip()
        client_data = df[df['cle_licence'] == str(cle_saisie).strip()]
        return client_data.iloc[0]['nom_client'] if not client_data.empty else None
    except: return None

# --- 3. INTERFACE DE CONNEXION ---
if st.session_state.role is None:
    st.title("🎙️ Language Lab")
    t1, t2 = st.tabs(["👨‍🏫 Professeur", "🎓 Élève"])
    with t1:
        cle = st.text_input("Clé d'activation :", type="password")
        if st.button("Connexion Prof"):
            nom = verifier_licence(cle)
            if nom: st.session_state.role = "Professeur"; st.session_state.nom_abonne = nom; st.rerun()
    with t2:
        nom_e = st.text_input("Ton prénom :")
        if st.button("Démarrer"):
            if nom_e: st.session_state.nom_eleve = nom_e; st.session_state.role = "Eleve"; st.rerun()

# --- 4. DASHBOARD PROFESSEUR ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.nom_abonne}")
    t_reg, t_cons, t_qr = st.tabs(["🎯 Réglages", "📝 Scénario", "📲 Partage"])
    with t_reg:
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.config["langue"] = st.selectbox("Langue :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"], index=["Anglais", "Néerlandais", "Allemand", "Espagnol"].index(st.session_state.config["langue"]))
            st.session_state.config["niveau"] = st.select_slider("Niveau CEFR :", ["A1", "A2", "B1", "B2"], value=st.session_state.config["niveau"])
        with col2:
            st.session_state.config["grammaire"] = st.text_input("Focus Grammaire :", value=st.session_state.config["grammaire"])
            st.session_state.config["mode"] = st.radio("Mode :", ["Interaction (Dialogue)", "Production continue"])
        st.session_state.config["role_ia"] = st.text_area("Rôle précis de l'IA :", value=st.session_state.config["role_ia"])
    with t_cons:
        st.session_state.config["consigne_eleve"] = st.text_area("Consigne élève :", value=st.session_state.config["consigne_eleve"])
    with t_qr:
        params = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "g": st.session_state.config["grammaire"], "c": st.session_state.config["consigne_eleve"]}
        url = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(params)
        st.image(qrcode.make(url).get_image(), width=180)

    if st.sidebar.button("🚀 Mode Élève"): st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"): st.session_state.role = None; st.rerun()

# --- 5. INTERFACE ÉLÈVE (CORRIGÉE) ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Hello {st.session_state.get('nom_eleve')} !")
    
    with st.expander("📝 Ta mission", expanded=True):
        st.write(st.session_state.config["consigne_eleve"])

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    audio_value = st.audio_input("Appuie et parle...")

    if audio_value:
        with st.spinner("Analyse..."):
            # 1. Transcription
            transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_value))
            texte_eleve = transcript.text
            st.session_state.messages.append({"role": "user", "content": texte_eleve})
            
            # 2. Réponse IA avec Scénario forcé
            sys_prompt = f"""
            {st.session_state.config['role_ia']}. 
            SCÉNARIO ACTUEL : {st.session_state.config['consigne_eleve']}.
            Tu dois parler EXCLUSIVEMENT en {st.session_state.config['langue']} au niveau {st.session_state.config['niveau']}.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages
            )
            reponse_ia = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": reponse_ia})

            # 3. Génération Audio MP3 compatible iPhone
            audio_gen = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia, response_format="mp3")
            
            # Affichage immédiat du texte et du son
            st.rerun()

    # Lecture Audio (Placée ici pour éviter le message "Erreur")
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        last_msg = st.session_state.messages[-1]["content"]
        # On génère le son uniquement pour le dernier message pour éviter les conflits
        audio_output = client.audio.speech.create(model="tts-1", voice="alloy", input=last_msg, response_format="mp3")
        st.audio(audio_output.content, format="audio/mpeg", autoplay=True)

    with st.sidebar:
        if st.button("📊 Bilan final"):
            p_bilan = f"Fais un bilan court sur le niveau {st.session_state.config['niveau']} (Aisance, Richesse, Intelligibilité)."
            bilan = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": p_bilan}] + st.session_state.messages)
            st.info(bilan.choices[0].message.content)
            st.download_button("📥 Télécharger", data=bilan.choices[0].message.content, file_name="bilan.txt")
        if st.button("⬅️ Retour"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.rerun()
