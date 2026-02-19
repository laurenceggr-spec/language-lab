import streamlit as st
import pandas as pd
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION & UI ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🇧🇪", layout="wide")

st.markdown("""
    <style>
    audio { height: 35px; width: 100%; }
    .stAudioInput { border: 2px solid #FF4B4B; border-radius: 15px; padding: 10px; background-color: #FFF5F5; }
    .element-container { overflow: hidden; }
    </style>
    """, unsafe_allow_html=True)

if "OPENAI_API_KEY" in st.secrets:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("🔑 Clé API absente des Secrets Streamlit.")
    st.stop()

SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
lang_map = {"Anglais": "en", "Néerlandais": "nl", "Allemand": "de", "Espagnol": "es"}

# Initialisation Session State
if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "last_processed_id" not in st.session_state: st.session_state.last_processed_id = None
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": st.query_params.get("l", "Anglais"),
        "niveau": st.query_params.get("n", "A2"),
        "grammaire": st.query_params.get("g", "Général"),
        "mode": st.query_params.get("m", "Interaction (Dialogue - EOAI)"),
        "consigne_eleve": st.query_params.get("c", "Présente-toi au tuteur."),
        "role_ia": "Tu es un tuteur de langue bienveillant pour le Tronc Commun (FWB). Focus UAA3."
    }

# Détection automatique du mode élève via URL
if any(k in st.query_params for k in ["l", "n", "c"]):
    st.session_state.role = "Eleve"

# --- 2. FONCTIONS ---
def verifier_licence(cle):
    try:
        df = pd.read_csv(SHEET_URL)
        df['cle_licence'] = df['cle_licence'].astype(str).str.strip()
        res = df[df['cle_licence'] == str(cle).strip()]
        return res.iloc[0]['nom_client'] if not res.empty else None
    except: return None

# --- 3. ACCÈS ---
if st.session_state.role is None:
    st.title("🎙️ Language Lab")
    t1, t2 = st.tabs(["👨‍🏫 Professeur", "🎓 Élève"])
    with t1:
        cle = st.text_input("Clé d'activation école :", type="password")
        if st.button("Connexion Professeur"):
            nom = verifier_licence(cle)
            if nom: st.session_state.role = "Professeur"; st.session_state.nom_abonne = nom; st.rerun()
    with t2:
        nom_e = st.text_input("Ton prénom :")
        if st.button("Démarrer la session"):
            if nom_e: st.session_state.nom_eleve = nom_e; st.session_state.role = "Eleve"; st.rerun()

# --- 4. DASHBOARD PROFESSEUR (RESTAURÉ & COMPLET) ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.get('nom_abonne', 'Abonné')}")
    t_reg, t_cons, t_qr = st.tabs(["🎯 Configuration", "📝 Scénario & Prompt", "📲 Partage"])
    
    with t_reg:
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.config["langue"] = st.selectbox("Langue cible :", list(lang_map.keys()), index=list(lang_map.keys()).index(st.session_state.config["langue"]))
            st.session_state.config["niveau"] = st.select_slider("Niveau CEFR :", ["A1", "A2", "B1", "B2"], value=st.session_state.config["niveau"])
        with col2:
            st.session_state.config["mode"] = st.selectbox("Type d'activité :", 
                ["Interaction (Dialogue - EOAI)", "Production continue (EOSI)", "Tutorat avec conseils d'amélioration"],
                index=0)
            st.session_state.config["grammaire"] = st.text_input("Attendus grammaticaux :", value=st.session_state.config["grammaire"])
    
    with t_cons:
        st.session_state.config["role_ia"] = st.text_area("Rôle de l'IA (Prompt pour le tuteur) :", value=st.session_state.config["role_ia"])
        st.session_state.config["consigne_eleve"] = st.text_area("Consigne affichée à l'élève :", value=st.session_state.config["consigne_eleve"])

    with t_qr:
        p = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "c": st.session_state.config["consigne_eleve"], "g": st.session_state.config["grammaire"], "m": st.session_state.config["mode"]}
        url = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(p)
        st.image(qrcode.make(url).get_image(), width=150, caption="Scan pour synchroniser")

    if st.sidebar.button("🚀 Lancer le mode Élève"): st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"): st.session_state.role = None; st.query_params.clear(); st.rerun()

# --- 5. INTERFACE ÉLÈVE (FIX ATTRIBUTEERROR) ---
elif st.session_state.role == "Eleve":
    # FIX : Utilisation de .get() pour éviter le crash si le nom est absent
    nom_affichage = st.session_state.get('nom_eleve', 'Élève')
    st.title(f"🎙️ Session de {nom_affichage}")
    st.info(f"📋 **Mission :** {st.session_state.config['consigne_eleve']}")

    if "current_audio" in st.session_state and st.session_state.current_audio:
        st.audio(st.session_state.current_audio, format="audio/mpeg", autoplay=True)
        st.session_state.current_audio = None 

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    audio_file = st.audio_input("Clique pour parler")

    if audio_file:
        audio_id = audio_file.size
        if st.session_state.last_processed_id != audio_id:
            with st.spinner("Analyse..."):
                code_l = lang_map.get(st.session_state.config["langue"], "en")
                trans = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_file), language=code_l)
                st.session_state.messages.append({"role": "user", "content": trans.text})
                
                sys_p = f"{st.session_state.config['role_ia']}. Mode: {st.session_state.config['mode']}. Scénario: {st.session_state.config['consigne_eleve']}. Langue: {st.session_state.config['langue']} (Niveau {st.session_state.config['niveau']}). Focus Grammaire: {st.session_state.config['grammaire']}."
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys_p}] + st.session_state.messages)
                txt_ia = resp.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": txt_ia})
                
                tts = client.audio.speech.create(model="tts-1", voice="alloy", input=txt_ia, response_format="mp3")
                st.session_state.current_audio = tts.content
                st.session_state.last_processed_id = audio_id
                st.rerun()

    with st.sidebar:
        st.header("🏁 Bilan final")
        if st.button("📊 GÉNÉRER MON BILAN FWB"):
            prompt_bilan = f"""Tu es un expert FWB. Analyse cette conversation. 
            Rédige un bilan sur : 1. AISANCE, 2. RICHESSE (Vocabulaire/Grammaire: {st.session_state.config['grammaire']}), 3. INTELLIGIBILITÉ. 
            Fais l'évaluation en français. Ne réponds pas au dialogue."""
            bilan_resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_bilan}, {"role": "user", "content": "Génère mon bilan."}] + st.session_state.messages)
            st.session_state.bilan_final = bilan_resp.choices[0].message.content
        
        if "bilan_final" in st.session_state:
            st.success("Bilan prêt")
            st.write(st.session_state.bilan_final)
            st.download_button("📥 Télécharger", data=st.session_state.bilan_final, file_name=f"bilan_{nom_affichage}.txt")

        if st.button("⬅️ Retour", key="btn_ret"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.query_params.clear(); st.rerun()
