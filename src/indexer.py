import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
import json
import os

# ============================================================
# CHEMINS ABSOLUS — calculés depuis la position de CE fichier
# ============================================================
# Peu importe le répertoire de travail (cwd) d'où le script est lancé
# (notebook avec cwd=notebooks/, ou `streamlit run` avec cwd=racine du
# projet) — ces chemins pointent toujours vers le même endroit réel.

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SRC_DIR)

CHROMA_PATH = os.path.join(_PROJECT_ROOT, "data", "chroma_db")
MODEL_NAME = "intfloat/multilingual-e5-base"


class E5EmbeddingFunction(EmbeddingFunction):
    """
    Wrapper autour de SentenceTransformer pour respecter le format d'entrée
    attendu par les modèles E5 : les documents indexés doivent être préfixés
    par 'passage: ', les requêtes de recherche par 'query: '. Sans ces
    préfixes, le modèle sort de son régime d'entraînement optimal et les
    distances perdent en discrimination entre pertinent et non pertinent.
    """

    def __init__(self, model_name=MODEL_NAME, mode="passage"):
        self.model = SentenceTransformer(model_name)
        self.mode = mode  # "passage" à l'indexation, "query" à la recherche

    def __call__(self, input: Documents) -> Embeddings:
        prefix = "query: " if self.mode == "query" else "passage: "
        prefixed = [prefix + text for text in input]
        embeddings = self.model.encode(prefixed, normalize_embeddings=True)
        return embeddings.tolist()


def get_chroma_collection(collection_name="essai_custom", force_recreate=False, mode="passage"):
    """
    mode="passage" : à utiliser pour indexer les chunks (02_indexing.ipynb)
    mode="query"   : à utiliser pour interroger la collection (03_retrieval.ipynb,
                     04_generation.ipynb, app/streamlit_app.py)
    """
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = E5EmbeddingFunction(mode=mode)

    if force_recreate:
        try:
            client.delete_collection(collection_name)
            print(f"Ancienne collection '{collection_name}' supprimée")
        except Exception:
            pass
        collection = client.create_collection(
            name=collection_name,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"}
        )
    else:
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=ef
        )
    return collection


def index_chunks(chunks, collection, categorie="administratif", filiere=None, annee="2025-2026"):
    """Embedde (avec préfixe 'passage: ') et indexe les chunks, métadonnées enrichies incluses."""
    ids = [c["chunk_id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [{
        "source_file": c["source_file"],
        "extractor_used": c["extractor_used"],
        "title": c.get("title") or "",
        "subtitle": c.get("subtitle") or "",
        "page_number": c.get("page_number") if c.get("page_number") is not None else -1,
        "total_pages": c.get("total_pages") or 1,
        "chunk_index": c["chunk_index"],
        "chunk_method": c["chunk_method"],
        "categorie": categorie,
        "filiere": filiere or "generale",
        "annee_academique": annee
    } for c in chunks]

    collection.add(ids=ids, documents=texts, metadatas=metadatas)
    return len(chunks)


def get_collection_status(collection_name="essai_custom"):
    """
    Utilitaire de diagnostic — affiche le chemin ChromaDB utilisé et le
    nombre de documents indexés. Pratique pour vérifier rapidement, depuis
    n'importe quel contexte (notebook, Streamlit, script), que la collection
    pointe bien vers la bonne base et qu'elle n'est pas vide.
    """
    print(f"CHROMA_PATH : {CHROMA_PATH}")
    print(f"Le dossier existe : {os.path.exists(CHROMA_PATH)}")

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        collection = client.get_collection(collection_name)
        print(f"Collection '{collection_name}' : {collection.count()} documents")
    except Exception as e:
        print(f"Collection '{collection_name}' introuvable : {e}")