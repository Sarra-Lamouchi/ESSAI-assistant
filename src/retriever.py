def search_top_k(collection, query, k=5):
    """
    Effectue une recherche sémantique et retourne les k meilleurs résultats.
    ATTENTION : la collection passée ici doit avoir été ouverte en mode="query"
    (get_chroma_collection(..., mode="query")) pour que le préfixe E5 correct
    soit appliqué à la requête.
    """
    res = collection.query(query_texts=[query], n_results=k)

    results = []
    for rank, (doc, meta, dist, chunk_id) in enumerate(
        zip(res["documents"][0], res["metadatas"][0], res["distances"][0], res["ids"][0]),
        start=1
    ):
        results.append({
            "rank": rank,
            "chunk_id": chunk_id,
            "distance": dist,
            "source_file": meta.get("source_file"),
            "title": meta.get("title"),
            "subtitle": meta.get("subtitle"),
            "page_number": meta.get("page_number"),
            "chunk_method": meta.get("chunk_method"),
            "text": doc,
        })
    return results


def print_top_k(collection, query, k=5, text_preview_chars=200):
    """Affiche lisiblement les top-k références pour une requête donnée."""
    results = search_top_k(collection, query, k)
    print(f"QUERY : {query}")
    print("=" * 100)
    for r in results:
        print(f"[{r['rank']}] dist={r['distance']:.4f} | {r['source_file']} | subtitle: {r['subtitle']}")
        print(f"    {r['text'][:text_preview_chars]}...")
        print()
    return results