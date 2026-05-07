import duckdb
from rank_bm25 import BM25Okapi

DB_PATH = "data/sepsis_atlas.duckdb"


def build_bm25_index():
    """
    Build a BM25 index from all stored source quotes.
    Returns (index, metadata_list, raw_texts).
    """
    conn = duckdb.connect(DB_PATH)
    rows = conn.execute(
        "SELECT evidence_id, source_quote, study_label, predictor, outcome FROM evidence"
    ).fetchall()
    conn.close()

    if not rows:
        return None, [], []

    corpus = [str(row[1]).lower().split() for row in rows]
    metadata = [
        {
            "evidence_id": row[0],
            "study_label": row[2],
            "predictor": row[3],
            "outcome": row[4],
        }
        for row in rows
    ]
    raw_texts = [str(row[1]) for row in rows]
    index = BM25Okapi(corpus)
    return index, metadata, raw_texts


def bm25_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Keyword search over stored source quotes.
    Returns top_k results sorted by BM25 relevance score.
    """
    index, metadata, raw_texts = build_bm25_index()

    if index is None:
        return []

    scores = index.get_scores(query.lower().split())
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    return [
        {
            **metadata[i],
            "text": raw_texts[i],
            "score": float(scores[i]),
        }
        for i in top_indices
        if scores[i] > 0
    ]
