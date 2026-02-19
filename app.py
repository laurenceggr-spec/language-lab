import streamlit as st
import pandas as pd
import openai
import qrcode
from io import BytesIO

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Language Lab - FWB", page_icon="🎙️", layout="wide")

SHEET_ID = "10CcT3xpWgyqye5ekI5_pJgaoBCbVfPQIDmIqfIM6sp8" 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Connexion sécurisée via les Secrets Streamlit
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Initialisation des variables de session
if "role" not in st.session_state: st.session_state.role = None
if "nom_eleve" not in st.session_state: st.session_state.nom_eleve = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "config" not in st.session_state:
    st.session_state.config = {
        "langue": "Anglais",
        "niveau": "A2",
        "grammaire": "Général",
        "mode": "Interaction (Dialogue)",
        "role_ia": "Tu es un tuteur de langue bienveillant pour des élèves du tronc commun."
    }

# --- 2. FONCTIONS ---
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
    
    tab1, tab2 = st.tabs(["👨‍🏫 Espace Professeur", "🎓 Espace Élève"])
    
    with tab1:
        cle = st.text_input("Clé d'activation école :", type="password", key="cle_prof")
        if st.button("Connexion Enseignant"):
            nom = verifier_licence(cle)
            if nom:
                st.session_state.role = "Professeur"
                st.session_state.nom_abonne = nom
                st.rerun()
            else: st.error("Clé invalide.")
            
    with tab2:
        nom_saisi = st.text_input("Entre ton prénom ou nom :", key="nom_saisie_eleve")
        if st.button("Commencer l'exercice"):
            if nom_saisi:
                st.session_state.nom_eleve = nom_saisi
                st.session_state.role = "Eleve"
                st.rerun()
            else: st.warning("N'oublie pas d'entrer ton nom !")

# --- 4. DASHBOARD PROFESSEUR ---
elif st.session_state.role == "Professeur":
    st.title(f"👨‍🏫 Dashboard - {st.session_state.nom_abonne}")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🎯 Réglages")
        st.session_state.config["langue"] = st.selectbox("Langue :", ["Anglais", "Néerlandais", "Allemand", "Espagnol"])
        st.session_state.config["niveau"] = st.select_slider("Niveau :", ["A1", "A2", "B1", "B2"])
        st.session_state.config["grammaire"] = st.text_input("Focus Grammatical :", value=st.session_state.config["grammaire"])
        st.session_state.config["mode"] = st.radio("Mode :", ["Interaction (Dialogue)", "Production continue"])
    with col_b:
        st.subheader("🤖 Rôle de l'IA")
        st.session_state.config["role_ia"] = st.text_area("Consigne :", value=st.session_state.config["role_ia"])
        qr = qrcode.make("https://language-lab.streamlit.app"); buf = BytesIO(); qr.save(buf)
        st.image(buf, width=150, caption="QR Code Classe")
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.role = None; st.rerun()

# --- 5. INTERFACE ÉLÈVE ---
elif st.session_state.role == "Eleve":
    st.title(f"🎙️ Hello {st.session_state.nom_eleve} !")
    st.caption(f"Langue : {st.session_state.config['langue']} | Niveau : {st.session_state.config['niveau']}")

    # Affichage du chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Entrée Audio
    audio_value = st.audio_input("Appuie pour parler")

    if audio_value:
        with st.spinner("L'IA réfléchit..."):
            # 1. Transcription
            transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_value.read()))
            texte_eleve = transcript.text
            st.session_state.messages.append({"role": "user", "content": texte_eleve})
            
            # 2. Réponse IA
            prompt_ia = f"{st.session_state.config['role_ia']}. Réponds en {st.session_state.config['langue']} au niveau {st.session_state.config['niveau']}."
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt_ia}] + 
                         [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            )
            reponse_ia = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
            
            # 3. Synthèse Vocale
            audio_res = client.audio.speech.create(model="tts-1", voice="alloy", input=reponse_ia)
            
            # Rerender pour afficher le nouveau message et l'audio
            st.rerun()

    # Lecture de la dernière réponse audio
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        last_msg = st.session_state.messages[-1]["content"]
        with st.spinner("Génération de la voix..."):
            audio_res = client.audio.speech.create(model="tts-1", voice="alloy", input=last_msg)
            # On ajoute un titre pour que l'élève voie le lecteur
            st.write("---")
            st.audio(audio_res.content, format="audio/mp3", autoplay=True)
            st.info("💡 Si le son ne se lance pas tout seul, appuyez sur Play ci-dessus.")
