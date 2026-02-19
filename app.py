import streamlit as st
import pandas as pd  # Corrigé ici
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION & SÉCURITÉ ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🇧🇪", layout="wide")

if "OPENAI_API_KEY" in st.secrets:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("🔑 Clé API absente des Secrets.")
    st.stop()

SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Initialisation Session State
if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None
if "micro_key" not in st.session_state: st.session_state.micro_key = 0 
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

# --- 4. DASHBOARD PROFESSEUR (FONCTIONS VALIDÉES) ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.nom_abonne}")
    t_reg, t_cons, t_qr = st.tabs(["🎯 Configuration", "📝 Scénario", "📲 Partage"])
    with t_reg:
        st.session_state.config["langue"] = st.selectbox("Langue cible :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"])
        st.session_state.config["niveau"] = st.select_slider("Niveau CEFR :", ["A1", "A2", "B1", "B2"])
        st.session_state.config["role_ia"] = st.text_area("Prompt caché IA :", value=st.session_state.config["role_ia"])
    with t_cons:
        st.session_state.config["consigne_eleve"] = st.text_area("Consigne élève :", value=st.session_state.config["consigne_eleve"])
    with t_qr:
        # QR Code Dynamique
        p = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "c": st.session_state.config["consigne_eleve"]}
        url = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(p)
        st.image(qrcode.make(url).get_image(), width=150)
    if st.sidebar.button("🚀 Mode Élève"): st.session_state.role = "Eleve"; st.rerun()

# --- 5. INTERFACE ÉLÈVE (MICRO RÉACTIF) ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Session de {st.session_state.get('nom_eleve')}")
    with st.expander("📖 Ta mission du jour", expanded=True):
        st.write(st.session_state.config["consigne_eleve"])

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    # LE FIX : On change la 'key' à chaque tour pour réveiller le micro
    audio_file = st.audio_input("Parle maintenant...", key=f"micro_{st.session_state.micro_key}")

    if audio_file:
        audio_id = audio_file.size
        if st.session_state.last_audio_id != audio_id:
            with st.spinner("Analyse..."):
                # Transcription
                trans = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_file))
                st.session_state.messages.append({"role": "user", "content": trans.text})
                
                # Réponse IA : On force le scénario et le prompt du prof
                sys_prompt = f"{st.session_state.config['role_ia']}. Scénario: {st.session_state.config['consigne_eleve']}. Langue: {st.session_state.config['langue']} (Niveau {st.session_state.config['niveau']})."
                response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages)
                reponse_ia = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
                
                # Audio TTS
                audio_res = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia, response_format="mp3")
                st.session_state.current_audio = audio_res.content
                st.session_state.last_audio_id = audio_id
                st.session_state.micro_key += 1 
                st.rerun()

    if "current_audio" in st.session_state and st.session_state.current_audio:
        st.audio(st.session_state.current_audio, format="audio/mpeg", autoplay=True)
        st.session_state.current_audio = None

    with st.sidebar:
        st.header("🏁 Bilan final")
        if st.button("📊 Générer mon bilan FWB"):
            # Analyse Aisance, Richesse, Intelligibilité
            p_bilan = f"Bilan pédagogique FWB sur le niveau {st.session_state.config['niveau']} (Aisance, Richesse, Intelligibilité)."
            bilan = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": p_bilan}] + st.session_state.messages)
            bilan_texte = bilan.choices[0].message.content
            st.info(bilan_texte)
            # Bouton de téléchargement
            st.download_button("📥 Télécharger (.txt)", data=bilan_texte, file_name=f"bilan_{st.session_state.nom_eleve}.txt")
        if st.button("⬅️ Retour"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.rerun()
