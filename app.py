import streamlit as st
import pandas as pd
import openai
import qrcode
import urllib.parse
from io import BytesIO

# --- 1. CONFIGURATION & SÉCURITÉ ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🇧🇪", layout="wide")

SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

query_params = st.query_params

# Initialisation Session State
if "role" not in st.session_state: st.session_state.role = None
if "messages" not in st.session_state: st.session_state.messages = []
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": query_params.get("l", "Anglais"),
        "niveau": query_params.get("n", "A2"),
        "grammaire": query_params.get("g", "Général"),
        "mode": "Interaction (Dialogue)",
        "consigne_eleve": query_params.get("c", "Présente-toi au tuteur."),
        "role_ia": "Tu es un tuteur de langue bienveillant pour le Tronc Commun (FWB). Focus sur l'UAA3 (interaction orale)."
    }

# --- 2. FONCTIONS CŒUR ---
def verifier_licence(cle_saisie):
    try:
        df = pd.read_csv(SHEET_URL)
        df['cle_licence'] = df['cle_licence'].astype(str).str.strip()
        client_data = df[df['cle_licence'] == str(cle_saisie).strip()]
        return client_data.iloc[0]['nom_client'] if not client_data.empty else None
    except: return None

def analyser_fwb(texte):
    # Analyse pédagogique discrète (Feedback immédiat)
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Donne un seul conseil pédagogique très court et bienveillant en français sur cette phrase d'élève."}] + [{"role": "user", "content": texte}]
    )
    return res.choices[0].message.content

# --- 3. ACCÈS ---
if st.session_state.role is None:
    st.title("🎙️ Language Lab")
    st.caption("Fédération Wallonie-Bruxelles - Portail Pédagogique")
    t1, t2 = st.tabs(["👨‍🏫 Espace Professeur", "🎓 Espace Élève"])
    
    with t1:
        cle = st.text_input("Clé d'activation école (via Google Sheets) :", type="password")
        if st.button("Connexion Sécurisée"):
            nom = verifier_licence(cle)
            if nom:
                st.session_state.role = "Professeur"; st.session_state.nom_abonne = nom; st.rerun()
            else: st.error("Clé invalide ou abonnement expiré.")
    with t2:
        nom_e = st.text_input("Prénom de l'élève :")
        if st.button("Démarrer la session"):
            if nom_e: st.session_state.nom_eleve = nom_e; st.session_state.role = "Eleve"; st.rerun()

# --- 4. DASHBOARD PROFESSEUR ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.nom_abonne}")
    t_reg, t_cons, t_qr = st.tabs(["🎯 Configuration Pédagogique", "📝 Consigne Scénarisée", "📲 QR Code Classe"])
    
    with t_reg:
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.config["langue"] = st.selectbox("Langue cible :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"], index=["Anglais", "Néerlandais", "Allemand", "Espagnol"].index(st.session_state.config["langue"]))
            st.session_state.config["niveau"] = st.select_slider("Niveau attendu (CEFR) :", ["A1", "A2", "B1", "B2"], value=st.session_state.config["niveau"])
        with col2:
            st.session_state.config["grammaire"] = st.text_input("Attentes spécifiques (Focus) :", value=st.session_state.config["grammaire"])
            st.session_state.config["mode"] = st.radio("Type d'activité :", ["Interaction (Dialogue)", "Production continue"])
        st.session_state.config["role_ia"] = st.text_area("Scénario pour l'IA (Prompt caché) :", value=st.session_state.config["role_ia"])

    with t_cons:
        st.session_state.config["consigne_eleve"] = st.text_area("Consigne affichée à l'élève :", value=st.session_state.config["consigne_eleve"])

    with t_qr:
        params = {"l": st.session_state.config["langue"], "n": st.session_state.config["niveau"], "g": st.session_state.config["grammaire"], "c": st.session_state.config["consigne_eleve"]}
        url = "https://language-lab.streamlit.app/?" + urllib.parse.urlencode(params)
        qr = qrcode.make(url); buf = BytesIO(); qr.save(buf)
        st.image(buf, width=180, caption="Scannez pour synchroniser les tablettes")

    if st.sidebar.button("🚀 Tester comme Élève"): st.session_state.role = "Eleve"; st.rerun()
    if st.sidebar.button("🚪 Déconnexion"): st.session_state.role = None; st.rerun()

# --- 5. INTERFACE ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Language Lab : {st.session_state.get('nom_eleve')}")
    
    with st.expander("📝 Ta mission du jour", expanded=True):
        st.write(st.session_state.config["consigne_eleve"])
        st.caption(f"Objectif : {st.session_state.config['niveau']} | Langue : {st.session_state.config['langue']}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    audio_value = st.audio_input("Appuie pour parler...")

    if audio_value:
        with st.spinner("L'IA t'écoute..."):
            audio_data = audio_value.read()
            transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_data))
            texte_eleve = transcript.text
            
            st.session_state.messages.append({"role": "user", "content": texte_eleve})
            with st.chat_message("user"): 
                st.markdown(texte_eleve)
                # Feedback pédagogique immédiat (Point 3)
                conseil = analyser_fwb(texte_eleve)
                st.caption(f"💡 Conseil : {conseil}")

            if st.session_state.config["mode"] == "Interaction (Dialogue)":
                sys_prompt = f"{st.session_state.config['role_ia']}. Langue: {st.session_state.config['langue']}. Niveau: {st.session_state.config['niveau']}. Focus: {st.session_state.config['grammaire']}."
                response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages)
                reponse_ia = response.choices[0].message.content
                
                with st.chat_message("assistant"):
                    st.markdown(reponse_ia)
                    audio_res = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia)
                    st.audio(audio_res.content, format="audio/mp3", autoplay=True)
                
                st.session_state.messages.append({"role": "assistant", "content": reponse_ia})

    # --- BARRE LATÉRALE : BILAN & TÉLÉCHARGEMENT ---
    with st.sidebar:
        st.header("🏁 Fin de session")
        if st.button("📊 Générer mon bilan FWB"):
            prompt_bilan = f"Analyse cette conversation selon les critères FWB : Aisance, Richesse, Intelligibilité. Niveau cible : {st.session_state.config['niveau']}."
            bilan = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_bilan}] + st.session_state.messages)
            bilan_texte = bilan.choices[0].message.content
            st.info(bilan_texte)
            
            # Bouton de téléchargement (Point 4)
            st.download_button("📥 Télécharger mon bilan (.txt)", data=bilan_texte, file_name=f"bilan_{st.session_state.nom_eleve}.txt")
        
        if st.button("⬅️ Retour"):
            st.session_state.messages = []; st.session_state.role = "Professeur"; st.rerun()
