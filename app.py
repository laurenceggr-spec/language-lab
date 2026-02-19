import streamlit as st
import pandas as pd
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION & UI ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🇧🇪", layout="wide")

# CSS pour épurer l'interface et masquer les barres inutiles
st.markdown("""
    <style>
    audio { height: 35px; width: 100%; }
    .stChatFloatingInputContainer { bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

if "OPENAI_API_KEY" in st.secrets:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("🔑 Clé API manquante dans les Secrets Streamlit.")
    st.stop()

# Connexion Sheets (Contrôle des abonnés)
SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Mapping des langues pour Whisper (Indispensable pour le Néerlandais)
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
        "mode": "Interaction (Dialogue)",
        "consigne_eleve": st.query_params.get("c", "Présente-toi au tuteur."),
        "role_ia": "Tu es un tuteur de langue bienveillant pour le Tronc Commun (FWB). Focus UAA3."
    }

# --- 2. FONCTION LICENCE (GOOGLE SHEETS) ---
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
    st.caption("Fédération Wallonie-Bruxelles - Tronc Commun")
    t1, t2 = st.tabs(["👨‍🏫 Professeur", "🎓 Élève"])
    with t1:
        cle = st.text_input("Clé d'activation école :", type="password")
        if st.button("Connexion Professeur"):
            nom = verifier_licence(cle)
            if nom:
                st.session_state.role = "Professeur"; st.session_state.nom_abonne = nom; st.rerun()
            else: st.error("Clé invalide.")
    with t2:
        nom_e = st.text_input("Ton prénom :")
        if st.button("Démarrer la session"):
            if nom_e: 
                st.session_state.nom_eleve = nom_e; st.session_state.role = "Eleve"; st.rerun()

# --- 4. DASHBOARD PROFESSEUR (VERROUILLÉ) ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Configuration - {st.session_state.nom_abonne}")
    t_reg, t_cons, t_qr = st.tabs(["🎯 Réglages", "📝 Scénario", "📲 Partage"])
    
    with t_reg:
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.config["langue"] = st.selectbox("Langue cible :", list(lang_map.keys()), index=list(lang_map.keys()).index(st.session_state.config["langue"]))
            st.session_state.config["niveau"] = st.select_slider("Niveau CEFR :", ["A1", "A2", "B1", "B2"], value=st.session_state.config["niveau"])
        with col2:
            st.session_state.config["grammaire"] = st.text_input("Focus grammatical :", value=st.session_state.config["grammaire"])
            st.session_state.config["role_ia"] = st.text_area("Rôle caché de l'IA :", value=st.session_state.config["role_ia"])

    with t_cons:
        st.session_state.config["consigne_eleve"] = st.text_area("Consigne affichée à l'élève :", value=st.session_state.config["consigne_eleve"])

    with t_qr:
        # QR Code Dynamique
        p = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "g": st.session_state.config["grammaire"], "c": st.session_state.config["consigne_eleve"]}
        url = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(p)
        st.image(qrcode.make(url).get_image(), width=180, caption="Scan pour synchroniser la classe")

    if st.sidebar.button("🚀 Lancer le mode Élève"): st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"): st.session_state.role = None; st.rerun()

# --- 5. INTERFACE ÉLÈVE (FIX AUDIO, NÉERLANDAIS & DOUBLONS) ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Session de {st.session_state.get('nom_eleve')}")
    
    with st.expander("📖 Ta mission du jour", expanded=True):
        st.write(st.session_state.config["consigne_eleve"])

    # 1. AUDIO IA (Correctif boucle)
    if "current_audio" in st.session_state and st.session_state.current_audio:
        st.audio(st.session_state.current_audio, format="audio/mpeg", autoplay=True)
        st.session_state.current_audio = None 

    # 2. CHAT
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    # 3. MICRO ÉLÈVE
    audio_file = st.audio_input("Appuie, parle, puis appuie sur Stop")

    if audio_file:
        audio_id = audio_file.size
        if st.session_state.last_processed_id != audio_id:
            with st.spinner("Analyse de ta réponse..."):
                # Transcription FORCÉE dans la langue (Correctif Néerlandais)
                code_langue = lang_map.get(st.session_state.config["langue"], "en")
                trans = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=("audio.wav", audio_file),
                    language=code_langue
                )
                st.session_state.messages.append({"role": "user", "content": trans.text})
                
                # Réponse IA (Verrouillage Scénario)
                sys_prompt = f"""{st.session_state.config['role_ia']}. 
                SCÉNARIO : {st.session_state.config['consigne_eleve']}.
                Langue : {st.session_state.config['langue']} (Niveau {st.session_state.config['niveau']}).
                Focus : {st.session_state.config['grammaire']}."""
                
                response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages)
                reponse_ia = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
                
                # TTS
                tts = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia, response_format="mp3")
                st.session_state.current_audio = tts.content
                st.session_state.last_processed_id = audio_id
                st.rerun()

    # --- BARRE LATÉRALE : BILAN & TÉLÉCHARGEMENT (VERROUILLÉS) ---
    with st.sidebar:
        st.header("🏁 Bilan final")
        if st.button("📊 Générer mon bilan FWB"):
            with st.spinner("Analyse..."):
                p_bilan = f"Fais un bilan court (Aisance, Richesse, Intelligibilité) pour le niveau {st.session_state.config['niveau']}."
                bilan = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": p_bilan}] + st.session_state.messages)
                bilan_texte = bilan.choices[0].message.content
                st.info(bilan_texte)
                st.download_button("📥 Télécharger (.txt)", data=bilan_texte, file_name=f"bilan_{st.session_state.nom_eleve}.txt")
        
        # FIX : Clé unique pour éviter l'erreur de duplication
        if st.button("⬅️ Retour", key="btn_retour_eleve"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.rerun()
