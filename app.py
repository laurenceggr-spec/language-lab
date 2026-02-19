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
    st.error("🔑 Clé API manquante dans les Secrets.")
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
        "mode": st.query_params.get("m", "Interaction (Dialogue)"),
        "consigne_eleve": st.query_params.get("c", "Présente-toi au tuteur."),
        "identite_ia": "Alex, un ami curieux et bienveillant",
        "role_ia": "Tu es un tuteur de langue bienveillant pour le Tronc Commun (FWB). Focus UAA3.",
        "email_prof": st.query_params.get("e", "")
    }

# --- 2. FONCTIONS ---
def verifier_licence(cle):
    try:
        df = pd.read_csv(SHEET_URL)
        df['cle_licence'] = df['cle_licence'].astype(str).str.strip()
        res = df[df['cle_licence'] == str(cle).strip()]
        return res.iloc[0]['nom_client'] if not res.empty else None
    except: return None

# --- 3. ACCÈS & NOM ÉLÈVE ---
if st.session_state.role is None or (st.session_state.role == "Eleve" and "nom_eleve" not in st.session_state):
    st.title("🎙️ Language Lab - FWB")
    t1, t2 = st.tabs(["👨‍🏫 Professeur", "🎓 Élève"])
    with t1:
        cle = st.text_input("Clé école :", type="password")
        if st.button("Connexion Professeur"):
            nom = verifier_licence(cle)
            if nom: st.session_state.role = "Professeur"; st.session_state.nom_abonne = nom; st.rerun()
    with t2:
        nom_e = st.text_input("Ton prénom pour cette session :")
        if st.button("Commencer la session"):
            if nom_e: 
                st.session_state.nom_eleve = nom_e
                st.session_state.role = "Eleve"
                st.rerun()

# --- 4. DASHBOARD PROFESSEUR (COMPLET) ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.get('nom_abonne')}")
    t_reg, t_cons, t_qr = st.tabs(["🎯 Configuration", "📝 Scénario & Identité", "📲 Partage"])
    
    with t_reg:
        st.session_state.config["email_prof"] = st.text_input("📧 Ton adresse mail (pour recevoir les bilans) :", value=st.session_state.config["email_prof"])
        st.session_state.config["langue"] = st.selectbox("Langue cible :", list(lang_map.keys()))
        st.session_state.config["niveau"] = st.select_slider("Niveau CEFR :", ["A1", "A2", "B1", "B2"])
        st.session_state.config["mode"] = st.selectbox("Type d'activité :", ["Interaction (Dialogue - EOAI)", "Production continue (EOSI)", "Tutorat avec conseils d'amélioration"])
        st.session_state.config["grammaire"] = st.text_input("Attendus grammaticaux :", value=st.session_state.config["grammaire"])
    
    with t_cons:
        st.session_state.config["identite_ia"] = st.text_input("Identité de l'IA (ex: Alex, un policier, etc.) :", value=st.session_state.config["identite_ia"])
        st.session_state.config["role_ia"] = st.text_area("Prompt caché pour l'IA :", value=st.session_state.config["role_ia"])
        st.session_state.config["consigne_eleve"] = st.text_area("Consigne affichée à l'élève :", value=st.session_state.config["consigne_eleve"])

    with t_qr:
        p = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "c": st.session_state.config["consigne_eleve"], "g": st.session_state.config["grammaire"], "e": st.session_state.config["email_prof"]}
        url = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(p)
        st.image(qrcode.make(url).get_image(), width=150)
        st.caption("Scan pour synchroniser les tablettes.")

    if st.sidebar.button("🚀 Mode Élève"): st.session_state.role = "Eleve"; st.rerun()

# --- 5. INTERFACE ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Session de {st.session_state.nom_eleve}")
    st.info(f"📋 **Ta mission :** {st.session_state.config['consigne_eleve']}")

    if "current_audio" in st.session_state and st.session_state.current_audio:
        st.audio(st.session_state.current_audio, format="audio/mpeg", autoplay=True)
        st.session_state.current_audio = None 

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    audio_file = st.audio_input("Appuie et parle au tuteur...")

    if audio_file:
        audio_id = audio_file.size
        if st.session_state.last_processed_id != audio_id:
            with st.spinner("L'IA écoute..."):
                code_l = lang_map.get(st.session_state.config["langue"], "en")
                trans = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_file), language=code_l)
                st.session_state.messages.append({"role": "user", "content": trans.text})
                
                sys_p = f"Tu es {st.session_state.config['identite_ia']}. {st.session_state.config['role_ia']}. Scénario: {st.session_state.config['consigne_eleve']}. Mode: {st.session_state.config['mode']}. Langue: {st.session_state.config['langue']} (Niveau {st.session_state.config['niveau']})."
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys_p}] + st.session_state.messages)
                txt_ia = resp.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": txt_ia})
                
                tts = client.audio.speech.create(model="tts-1", voice="alloy", input=txt_ia, response_format="mp3")
                st.session_state.current_audio = tts.content
                st.session_state.last_processed_id = audio_id
                st.rerun()

    with st.sidebar:
        st.header("🏁 Bilan de session")
        if st.button("📊 GÉNÉRER MON BILAN FINAL"):
            with st.spinner("Analyse..."):
                p_bilan = f"""Tu es un expert FWB. Analyse la conversation.
                Rédige un bilan pédagogique s'adressant DIRECTEMENT à l'élève (utilise 'TU').
                Évalue sur : 1. TON AISANCE, 2. TA RICHESSE (Vocabulaire et Grammaire: {st.session_state.config['grammaire']}), 3. TON INTELLIGIBILITÉ.
                Réponds en français."""
                bilan_resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": p_bilan}] + st.session_state.messages)
                bilan_final = bilan_resp.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": f"🎯 **TON BILAN PERSONNEL :**\n\n{bilan_final}"})
                st.session_state.bilan_txt = bilan_final
                st.rerun()
        
        if "bilan_txt" in st.session_state:
            st.download_button("📥 Télécharger mon bilan (.txt)", data=st.session_state.bilan_txt, file_name=f"bilan_{st.session_state.nom_eleve}.txt")
            
            if st.session_state.config["email_prof"]:
                sujet = urllib.parse.quote(f"Bilan Language Lab - {st.session_state.nom_eleve}")
                corps = urllib.parse.quote(st.session_state.bilan_txt)
                mailto_link = f"mailto:{st.session_state.config['email_prof']}?subject={sujet}&body={corps}"
                st.markdown(f'<a href="{mailto_link}"><button style="width:100%; border-radius:10px; background-color:#4CAF50; color:white; padding:10px; border:none; cursor:pointer;">📧 Envoyer au professeur</button></a>', unsafe_allow_html=True)

        if st.button("⬅️ Quitter / Nouveau"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; del st.session_state.nom_eleve; st.rerun()
