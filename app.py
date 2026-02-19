import streamlit as st
import pandas as pd
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION & UI ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🇧🇪", layout="wide")

# CSS pour un bouton micro plus clair et suppression des barres de défilement
st.markdown("""
    <style>
    /* Style du lecteur audio */
    audio { height: 40px; width: 100%; border-radius: 20px; }
    /* Mise en évidence du micro */
    .stAudioInput { 
        border: 2px solid #FF4B4B; 
        border-radius: 15px; 
        padding: 10px;
        background-color: #FFF5F5;
    }
    /* Supprimer scrollbars inutiles */
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

# Session State
if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "last_processed_id" not in st.session_state: st.session_state.last_processed_id = None
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": st.query_params.get("l", "Anglais"),
        "niveau": st.query_params.get("n", "A2"),
        "grammaire": st.query_params.get("g", "Général"),
        "consigne_eleve": st.query_params.get("c", "Présente-toi au tuteur."),
        "role_ia": "Tu es un tuteur de langue bienveillant pour le Tronc Commun (FWB). Focus UAA3."
    }

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
        cle = st.text_input("Clé école :", type="password")
        if st.button("Connexion Professeur"):
            nom = verifier_licence(cle)
            if nom: st.session_state.role = "Professeur"; st.session_state.nom_abonne = nom; st.rerun()
    with t2:
        nom_e = st.text_input("Prénom :")
        if st.button("Démarrer"):
            if nom_e: st.session_state.nom_eleve = nom_e; st.session_state.role = "Eleve"; st.rerun()

# --- 4. PROFESSEUR ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Configuration - {st.session_state.nom_abonne}")
    st.session_state.config["langue"] = st.selectbox("Langue :", list(lang_map.keys()))
    st.session_state.config["niveau"] = st.select_slider("Niveau :", ["A1", "A2", "B1", "B2"], value=st.session_state.config["niveau"])
    st.session_state.config["consigne_eleve"] = st.text_area("Consigne scénarisée :", value=st.session_state.config["consigne_eleve"])
    
    p = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "c": st.session_state.config["consigne_eleve"]}
    url = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(p)
    st.image(qrcode.make(url).get_image(), width=150, caption="QR Code Classe")
    
    if st.sidebar.button("🚀 Mode Élève"): st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"): st.session_state.role = None; st.rerun()

# --- 5. ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Session de {st.session_state.nom_eleve}")
    st.info(f"📋 **Mission :** {st.session_state.config['consigne_eleve']}")

    # Lecture Audio IA
    if "current_audio" in st.session_state and st.session_state.current_audio:
        st.audio(st.session_state.current_audio, format="audio/mpeg", autoplay=True)
        st.session_state.current_audio = None 

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    # Zone Micro
    audio_file = st.audio_input("Clique sur le micro pour parler")

    if audio_file:
        audio_id = audio_file.size
        if st.session_state.last_processed_id != audio_id:
            with st.spinner("Analyse..."):
                code_l = lang_map.get(st.session_state.config["langue"], "en")
                trans = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_file), language=code_l)
                st.session_state.messages.append({"role": "user", "content": trans.text})
                
                sys_p = f"{st.session_state.config['role_ia']}. SCÉNARIO: {st.session_state.config['consigne_eleve']}. Langue: {st.session_state.config['langue']}."
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys_p}] + st.session_state.messages)
                txt_ia = resp.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": txt_ia})
                
                tts = client.audio.speech.create(model="tts-1", voice="alloy", input=txt_ia, response_format="mp3")
                st.session_state.current_audio = tts.content
                st.session_state.last_processed_id = audio_id
                st.rerun()

    with st.sidebar:
        st.header("🏁 Fin de session")
        if st.button("📊 GÉNÉRER MON BILAN FINAL"):
            with st.spinner("L'IA analyse tes compétences..."):
                # PROMPT DE BILAN FORCÉ (Hors dialogue)
                prompt_bilan = f"""
                Tu n'es plus le tuteur, tu es un expert certificateur FWB. 
                Analyse la conversation précédente de l'élève. 
                Rédige un bilan pédagogique STRICTEMENT sur ces 3 points :
                1. AISANCE (Fluidité)
                2. RICHESSE (Vocabulaire et Grammaire {st.session_state.config['grammaire']})
                3. INTELLIGIBILITÉ (Prononciation)
                Ne réponds pas au dialogue, fais uniquement l'évaluation en français.
                """
                bilan_resp = client.chat.completions.create(
                    model="gpt-4o-mini", 
                    messages=[{"role": "system", "content": prompt_bilan}, {"role": "user", "content": "Génère mon bilan maintenant."}] + st.session_state.messages
                )
                st.session_state.bilan_final = bilan_resp.choices[0].message.content
        
        if "bilan_final" in st.session_state:
            st.success("Bilan généré :")
            st.write(st.session_state.bilan_final)
            st.download_button("📥 Télécharger mon bilan", data=st.session_state.bilan_final, file_name="bilan_fwb.txt")

        if st.button("⬅️ Retour", key="btn_ret"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.rerun()
