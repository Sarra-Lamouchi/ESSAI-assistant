import json
import re
import os
from rank_bm25 import BM25Okapi

# ============================================================
# CHEMINS ABSOLUS — même logique que indexer.py
# ============================================================

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SRC_DIR)
DEFAULT_CHUNKS_PATH = os.path.join(_PROJECT_ROOT, "data", "processed", "chunks", "custom_chunks.jsonl")


def load_chunks_for_bm25(chunks_path=None):
    if chunks_path is None:
        chunks_path = DEFAULT_CHUNKS_PATH
    with open(chunks_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# ============================================================
# DICTIONNAIRE D'ABRÉVIATIONS ÉTUDIANTES
# ============================================================

ABBREVIATION_DICT = {
    "pfa": "atelier de statistique",
    "ds": "devoir surveillé",
    "cc": "contrôle continu",
    "sp": "session principale",
    "sc": "session de contrôle",
    "ue": "unité d'enseignement panier",
    "td": "travaux dirigés",
    "tp": "travaux pratiques",
    "ipei": "institut préparatoire aux études d'ingénieur",
    "cin": "carte d'identité nationale",
    "coes": "commission d'organisation des examens et des surveillances",
    "essai": "école supérieure de la statistique et de l'analyse de l'information",
    "ensae": "école nationale de la statistique et de l'administration économique",
    "ensai": "école nationale de la statistique et de l'analyse de l'information",
    "deadline": "date limite",
    "exam": "examen",
    "asia": "Association ASIA",
    "emlc": "ESSAI Machine Learning Club",
    "dd" : "Double Diplôme",
    "inscrit": "inscription",
    "l'inscrit": "inscription",
}


def expand_query(query, abbrev_dict=ABBREVIATION_DICT):
    """
    Expansion ADDITIVE : détecte les abréviations dans la requête et
    ajoute leurs termes d'expansion À LA FIN (le texte original est
    conservé intact). Utilisée pour hybrid_search (dense + BM25) —
    utile ici car ajouter des mots ne "trompe" pas ces deux moteurs
    de la même façon qu'un cross-encoder.
    """
    words = re.findall(r"\w+", query.lower())
    expansions = []
    for word in words:
        if word in abbrev_dict and abbrev_dict[word] not in expansions:
            expansions.append(abbrev_dict[word])

    if expansions:
        return query + " " + " ".join(expansions)
    return query


def canonicalize_query(query, abbrev_dict=ABBREVIATION_DICT):
    """
    Remplacement CANONIQUE : remplace chaque abréviation par son terme
    complet, SANS garder l'abréviation brute dans la requête. Utilisée
    uniquement avant le reranker (cross-encoder) — un modèle qui compare
    la requête et le texte littéralement peut être trompé par une
    abréviation ambiguë (ex: confond "pfa" avec "pfe") même quand on a
    juste ajouté du texte à côté (cas de expand_query). Le remplacement
    complet élimine cette ambiguïté à la source.
    """
    words = query.split()
    canonical_words = []
    for w in words:
        w_clean = re.sub(r"[^\wàâäéèêëïîôöùûüç]", "", w.lower())
        if w_clean in abbrev_dict:
            canonical_words.append(abbrev_dict[w_clean])
        else:
            canonical_words.append(w)
    return " ".join(canonical_words)


def simple_tokenize(text):
    return re.findall(r"[a-zàâäéèêëïîôöùûüç0-9]+", text.lower())


class BM25Index:
    def __init__(self, chunks):
        self.chunks = chunks
        self.chunk_ids = [c["chunk_id"] for c in chunks]
        tokenized_corpus = [simple_tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query, k=10):
        tokenized_query = simple_tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        ranked = sorted(zip(self.chunk_ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:k]


def reciprocal_rank_fusion(dense_results, bm25_results, k=60, top_k=10,
                             dense_weight=1.5, bm25_weight=1.0):
    """
    RRF pondéré : le dense search a plus de poids par défaut (observé plus
    fiable sur ce corpus) — BM25 sert de correctif plutôt que de
    partenaire à égalité.
    """
    rrf_scores = {}
    for rank, r in enumerate(dense_results, start=1):
        cid = r["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0) + dense_weight / (k + rank)
    for rank, (cid, score) in enumerate(bm25_results, start=1):
        rrf_scores[cid] = rrf_scores.get(cid, 0) + bm25_weight / (k + rank)
    fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return fused[:top_k]


def hybrid_search(collection, bm25_index, chunks_by_id, query, k=10,
                   dense_k=20, bm25_k=20, use_expansion=True, distance_threshold=0.35):
    """
    Retourne (results, status).
    status = "hors_corpus" si même le meilleur résultat dense est trop
    loin de la requête (rien d'assez proche dans le corpus) — permet au
    pipeline de génération de court-circuiter avant même le reranking/LLM.
    status = "ok" sinon.
    """
    search_query = expand_query(query) if use_expansion else query

    dense_res = collection.query(query_texts=[search_query], n_results=dense_k)

    distances = dense_res["distances"][0] if dense_res["distances"] else []
    best_distance = min(distances) if distances else 1.0
    if best_distance > distance_threshold:
        return [], "hors_corpus"

    dense_results = [
        {"chunk_id": cid, "distance": dist}
        for cid, dist in zip(dense_res["ids"][0], dense_res["distances"][0])
    ]
    bm25_results = bm25_index.search(search_query, k=bm25_k)
    fused = reciprocal_rank_fusion(dense_results, bm25_results, top_k=k)

    results = []
    for rank, (chunk_id, rrf_score) in enumerate(fused, start=1):
        chunk = chunks_by_id.get(chunk_id)
        if chunk:
            results.append({
                "rank": rank,
                "chunk_id": chunk_id,
                "rrf_score": rrf_score,
                "source_file": chunk["source_file"],
                "subtitle": chunk.get("subtitle"),
                "text": chunk["text"],
            })
    return results, "ok"


def print_hybrid_results(results, query, expanded_query=None, text_preview_chars=150):
    print(f"QUERY : {query}")
    if expanded_query and expanded_query != query:
        print(f"EXPANDED : {expanded_query}")
    print("=" * 100)
    for r in results:
        print(f"[{r['rank']}] rrf={r['rrf_score']:.5f} | {r['source_file']} | subtitle: {r['subtitle']}")
        print(f"    {r['text'][:text_preview_chars]}...")
    print()