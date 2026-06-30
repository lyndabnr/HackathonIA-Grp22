"""
TechCorp Financial Assistant — Interface de chat
Lancement : streamlit run app.py
"""
import json
import time

import requests
import streamlit as st

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "phi35-financial"

st.set_page_config(page_title="TechCorp Financial Assistant", page_icon="💬", layout="centered")


def check_server() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def stream_response(prompt: str, history: list[dict]):
    """Stream tokens from the Ollama /api/chat endpoint."""
    payload = {
        "model": MODEL_NAME,
        "messages": history + [{"role": "user", "content": prompt}],
        "stream": True,
    }
    with requests.post(f"{OLLAMA_URL}/api/chat", json=payload, stream=True, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content
            if chunk.get("done"):
                break


# ---------- UI ----------
st.title("💬 TechCorp Financial Assistant")

server_ok = check_server()
status_col1, status_col2 = st.columns([1, 4])
with status_col1:
    st.markdown("🟢 **Connecté**" if server_ok else "🔴 **Déconnecté**")
with status_col2:
    st.caption(f"Serveur d'inférence : {OLLAMA_URL} — modèle `{MODEL_NAME}`")

if not server_ok:
    st.error(
        "Impossible de joindre le serveur Ollama. Vérifiez qu'il tourne "
        f"({OLLAMA_URL}) et que le modèle `{MODEL_NAME}` a bien été créé "
        "(`ollama create phi35-financial -f ollama_server/Modelfile`)."
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Posez votre question financière...", disabled=not server_ok)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            for token in stream_response(prompt, st.session_state.messages[:-1]):
                full_response += token
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except requests.exceptions.RequestException as e:
            full_response = f"⚠️ Erreur de communication avec le serveur : {e}"
            placeholder.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})

with st.sidebar:
    st.header("Session")
    if st.button("🗑️ Effacer l'historique"):
        st.session_state.messages = []
        st.rerun()
    st.caption(f"{len(st.session_state.messages)} message(s) dans l'historique")
    st.divider()
    st.caption("Statut serveur rafraîchi à chaque interaction.")
