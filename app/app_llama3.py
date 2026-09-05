import sys
import os
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from indexer import get_chroma_collection
from hybrid_retriever import load_chunks_for_bm25, BM25Index, hybrid_search, canonicalize_query
from reranker import rerank_with_fallback
from generator_llama3 import RAGGeneratorLlama3
from greetings import detect_greeting, get_greeting_response
from conventions import detect_convention_request, get_convention_response


# ============================================================
# Questions suggérées
# ============================================================
SUGGESTED_QUESTIONS = [
    "Donner la convention de stage d’insertion ",
    "Donner la convention de stage d’ingénieur ",
    "Quels sont les documents nécessaires pour le PFE ?",
    "Donner les informations nécessaires concernant le double diplôme",
]


# ============================================================
# Chargement du pipeline
# ============================================================

@st.cache_resource
def load_pipeline():
    collection = get_chroma_collection(collection_name="essai_custom", force_recreate=False, mode="query")
    chunks_list = load_chunks_for_bm25()
    chunks_by_id = {c["chunk_id"]: c for c in chunks_list}
    bm25_index = BM25Index(chunks_list)
    generator = RAGGeneratorLlama3(max_memory_turns=5, ollama_model="llama3")
    return collection, bm25_index, chunks_by_id, generator


collection, bm25_index, chunks_by_id, generator = load_pipeline()


# ============================================================
# Fonction principale de question-réponse
# ============================================================

def ask(session_id, question, k_hybrid=10, k_final=3):
    greeting_category = detect_greeting(question)
    if greeting_category:
        answer = get_greeting_response(greeting_category)
        return answer, [], None

    convention_type = detect_convention_request(question)
    if convention_type:
        answer = get_convention_response(convention_type)
        return answer, [], None

    canonical_q = canonicalize_query(question)
    hybrid_results, status = hybrid_search(collection, bm25_index, chunks_by_id, canonical_q, k=k_hybrid)

    if status == "hors_corpus":
        answer = ("Je ne trouve pas d'information sur ce sujet dans les documents de l'ESSAI. "
                   "Essayez de reformuler votre question.")
        return answer, [], None

    final_chunks = rerank_with_fallback(canonical_q, hybrid_results, top_k=k_final)
    answer, elapsed = generator.generate(session_id, question, final_chunks)
    return answer, final_chunks, elapsed


# ============================================================
# Configuration de la page + thème bleu foncé (identique à l'app principale)
# ============================================================

st.set_page_config(page_title="Assistant ESSAI (Llama3)", page_icon="🎓", layout="centered")

CUSTOM_CSS = """
<style>
:root {
    --navy-dark: #0a1929;
    --navy-mid: #0f2942;
    --navy-light: #1a3a5c;
    --accent-blue: #2e7dd6;
    --accent-blue-hover: #4a94ea;
    --text-light: #e8eef5;
    --text-muted: #8fa3bd;
}

.stApp {
    background: linear-gradient(180deg, var(--navy-dark) 0%, #081420 100%);
    color: var(--text-light);
}

section[data-testid="stSidebar"] {
    background-color: var(--navy-mid);
    border-right: 1px solid var(--navy-light);
}
section[data-testid="stSidebar"] * {
    color: var(--text-light) !important;
}

h1 {
    color: var(--text-light) !important;
    font-weight: 700;
}

.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--text-muted) !important;
}

[data-testid="stChatMessage"] {
    background-color: var(--navy-mid);
    border: 1px solid var(--navy-light);
    border-radius: 12px;
    padding: 4px 8px;
    margin-bottom: 8px;
}

[data-testid="stChatInput"] textarea {
    background-color: var(--navy-mid) !important;
    color: var(--text-light) !important;
    border: 1px solid var(--navy-light) !important;
    border-radius: 10px !important;
}
[data-testid="stChatInput"] {
    background-color: var(--navy-dark) !important;
    border-top: 1px solid var(--navy-light);
}

.stButton button {
    background-color: var(--accent-blue) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600;
    transition: background-color 0.2s ease;
    min-height: 56px;
    white-space: normal;
    word-wrap: break-word;
    margin-bottom: 6px;
}
.stButton button:hover {
    background-color: var(--accent-blue-hover) !important;
}

hr {
    border-color: var(--navy-light) !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
# Interface
# ============================================================

st.title("🎓 Assistant ESSAI — Test Llama3")
st.caption("Version de test utilisant Llama3 en local via Ollama.")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("⚙️ Options")
    if st.button("🔄 Réinitialiser la conversation"):
        generator.reset_session(st.session_state.session_id)
        st.session_state.messages = []
        st.rerun()

# Affichage de l'historique
for msg in st.session_state.messages:
    avatar = "🧑‍🎓" if msg["role"] == "user" else "🎓"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ============================================================
# Suggestions — empilées verticalement, taille uniforme
# ============================================================
pending_question = None

if len(st.session_state.messages) == 0:
    st.markdown("**💡 Quelques questions pour commencer :**")
    for suggestion in SUGGESTED_QUESTIONS:
        if st.button(suggestion, use_container_width=True, key=f"suggestion_{suggestion}"):
            pending_question = suggestion

typed_question = st.chat_input("Pose ta question ici...")
question = typed_question or pending_question

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("Recherche en cours (Llama3 local)..."):
            answer, chunks, elapsed = ask(st.session_state.session_id, question)

        st.markdown(answer)
        if elapsed is not None:
            st.caption(f"⏱️ {elapsed:.2f}s — llama3 (Ollama)")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
    })

    st.rerun()