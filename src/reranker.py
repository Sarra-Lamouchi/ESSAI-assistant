from sentence_transformers import CrossEncoder

RERANKER_MODEL = "BAAI/bge-reranker-base"

_reranker_instance = None


def get_reranker():
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = CrossEncoder(RERANKER_MODEL, max_length=512)
    return _reranker_instance


def rerank(query, candidates, top_k=5):
    """
    Reclasse les candidats via cross-encoder (lit requête + texte ensemble,
    plus précis qu'un simple score de similarité vectorielle).
    """
    if not candidates:
        return []

    reranker = get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)

    scored = list(zip(candidates, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    reranked = []
    for new_rank, (candidate, score) in enumerate(scored[:top_k], start=1):
        reranked.append({
            **candidate,
            "rerank_score": float(score),
            "original_rank": candidate.get("rank"),
            "rank": new_rank,
        })
    return reranked


def rerank_with_fallback(query, candidates, top_k=5, confidence_threshold=0.15):
    """
    Applique le reranking, mais revient au classement hybrid original si le
    meilleur score de reranking reste sous le seuil de confiance — signe
    que le cross-encoder ne "comprend" pas la requête (jargon/abréviation
    mal canonisée) et risque de dégrader un résultat déjà correct.
    """
    if not candidates:
        return []

    reranked = rerank(query, candidates, top_k=top_k)

    if not reranked or reranked[0]["rerank_score"] < confidence_threshold:
        fallback = candidates[:top_k]
        for r in fallback:
            r["rerank_score"] = None
            r["fallback_used"] = True
        return fallback

    for r in reranked:
        r["fallback_used"] = False
    return reranked


def print_reranked_results(results, query, text_preview_chars=150):
    print(f"QUERY : {query}")
    print("=" * 100)
    for r in results:
        score_str = f"{r['rerank_score']:.4f}" if r.get("rerank_score") is not None else "N/A (fallback)"
        print(f"[{r['rank']}] rerank_score={score_str} "
              f"(rang hybrid initial: {r.get('original_rank')}) | {r['source_file']} | subtitle: {r['subtitle']}")
        print(f"    {r['text'][:text_preview_chars]}...")
    print()