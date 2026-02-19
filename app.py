import streamlit as st
import pandas as pd
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION & SÉCURITÉ ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🇧🇪", layout="wide")

# Système de récupération de clé sécurisé
if "OPENAI_API_KEY" in st.secrets:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("🔑 Erreur : La clé API est absente des Secrets Streamlit.")
    st.stop()

# Accès Google Sheets (Contrôle des abonnés)
SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Initialisation des variables de session (Verrous audio inclus)
if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": st.query_params.get("l", "Anglais"),
        "niveau": st.query_params.get("n", "A2"),
        "grammaire": st.query_params.get("g", "Général"),
        "mode": "Interaction (Dialogue)",
        "consigne_eleve": st.query_params.get("c", "Présente-toi au tuteur."),
        "role_ia": "Tu es un tuteur de langue bienveillant pour le Tronc Commun (FWB). Focus UAA3."
    }

# --- 2. FONCTIONS VALIDÉES (LICENCE) ---
def verifier_licence(cle_saisie):
    try:
        df = pd.read_csv(SHEET_URL)
        df['cle_licence'] = df['cle_licence'].astype(str).str.strip()
        client_data = df[df['cle_licence'] == str(cle_saisie).strip()]
        return client_data.iloc[0]['nom_client'] if not client_data.empty else None
    except: return None

# --- 3. ACCÈS (PROF / ÉLÈVE) ---
if st.session_state.role is None:
    st.title("🎙️ Language Lab")
    st.caption("Portail Pédagogique - Fédération Wallonie-Bruxelles")
    t1, t2 = st.tabs(["👨‍🏫 Espace Professeur", "🎓 Espace Élève"])
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
            if nom_e: st.session_state.nom_eleve = nom_e; st.session_state.role = "Eleve"; st.rerun()

# --- 4. DASHBOARD PROFESSEUR (FONCTIONS COMPLÈTES) ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.nom_abonne}")
    t_reg, t_cons, t_qr = st.tabs(["🎯 Configuration Pédagogique", "📝 Scénario & Consignes", "📲 Partage Classe"])
    
    with t_reg:
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.config["langue"] = st.selectbox("Langue cible :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"], index=0)
            st.session_state.config["niveau"] = st.select_slider("Niveau CEFR attendu :", ["A1", "A2", "B1", "B2"])
        with col2:
            st.session_state.config["grammaire"] = st.text_input("Focus grammatical (ex: inversion) :", value=st.session_state.config["grammaire"])
            st.session_state.config["mode"] = st.radio("Mode d'activité :", ["Interaction (Dialogue)", "Production continue"])
        st.session_state.config["role_ia"] = st.text_area("Rôle de l'IA (Prompt Prof) :", value=st.session_state.config["role_ia"])

    with t_cons:
        st.session_state.config["consigne_eleve"] = st.text_area("Consigne affichée à l'élève :", value=st.session_state.config["consigne_eleve"])

    with t_qr:
        # Génération du lien dynamique avec paramètres
        p = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "g": st.session_state.config["grammaire"], "c": st.session_state.config["consigne_eleve"]}
        full_url = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(p)
        qr_img = qrcode.make(full_url)
        buf = BytesIO(); qr_img.save(buf)
        st.image(buf, width=150, caption="Scan pour synchroniser les tablettes")

    if st.sidebar.button("🚀 Lancer le mode Élève"): st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"): st.session_state.role = None; st.rerun()

# --- 5. INTERFACE ÉLÈVE (AUDIO SÉCURISÉ & SCÉNARIO) ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Session de {st.session_state.get('nom_eleve')}")
    
    with st.expander("📖 Ta mission du jour", expanded=True):
        st.write(st.session_state.config["consigne_eleve"])
        st.caption(f"Objectif : {st.session_state.config['niveau']} | Langue : {st.session_state.config['langue']}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    audio_file = st.audio_input("Parle maintenant...")

    # Système anti-boucle par ID de fichier
    if audio_file:
        audio_id = audio_file.size
        if st.session_state.last_audio_id != audio_id:
            with st.spinner("L'IA prépare sa réponse..."):
                # Transcription Whisper
                trans = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_file))
                st.session_state.messages.append({"role": "user", "content": trans.text})
                
                # Réponse GPT forcée par le scénario du prof
                sys_prompt = f"""{st.session_state.config['role_ia']}. 
                SCÉNARIO : {st.session_state.config['consigne_eleve']}.
                Tu parles EXCLUSIVEMENT en {st.session_state.config['langue']} au niveau {st.session_state.config['niveau']}.
                Focus : {st.session_state.config['grammaire']}."""
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages
                )
                reponse_ia = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
                
                # Génération audio TTS format MP3 pour Safari
                audio_res = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia, response_format="mp3")
                st.session_state.current_audio = audio_res.content
                st.session_state.last_audio_id = audio_id
                st.rerun()

    # Lecture audio (Une seule fois par réponse)
    if "current_audio" in st.session_state and st.session_state.current_audio:
        st.audio(st.session_state.current_audio, format="audio/mpeg", autoplay=True)
        st.session_state.current_audio = None 

    # --- BARRE LATÉRALE : BILAN PÉDAGOGIQUE FWB & TÉLÉCHARGEMENT ---
    with st.sidebar:
        st.header("🏁 Fin de l'exercice")
        if st.button("📊 Générer mon bilan final"):
            with st.spinner("Analyse des compétences..."):
                p_bilan = f"Fais un bilan court pour l'élève sur son niveau {st.session_state.config['niveau']}. Analyse l'Aisance, la Richesse et l'Intelligibilité selon les critères FWB."
                bilan_resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": p_bilan}] + st.session_state.messages)
                bilan_texte = bilan_resp.choices[0].message.content
                st.info(bilan_texte)
                # Téléchargement validé
                st.download_button("📥 Télécharger mon bilan (.txt)", data=bilan_texte, file_name=f"bilan_{st.session_state.nom_eleve}.txt")
        
        if st.button("⬅️ Quitter la session"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.rerun()
