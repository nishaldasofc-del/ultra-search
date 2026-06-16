"""
Reranker — Reciprocal Rank Fusion (RRF) hybrid scoring.

Combines vector search results and BM25 results into a single ranked list.
RRF formula: score(d) = Σ 1 / (k + rank(d))
where k=60 is the standard constant that dampens high-rank outliers.

No ML model needed — pure math, zero cost, works better than either
system alone for most queries.
"""

from typing import List, Dict, Optional


RRF_K = 60   # standard RRF constant


def reciprocal_rank_fusion(
    vector_results: List[Dict],
    bm25_results:   List[Dict],
    vector_weight:  float = 0.6,
    bm25_weight:    float = 0.4,
    top_k:          int   = 20,
) -> List[Dict]:
    """
    Merge two ranked lists using weighted RRF.

    vector_results: from Qdrant, each has 'url', '_score', payload fields
    bm25_results:   from PostgreSQL FTS, each has 'url', 'bm25_rank', etc.
    """
    scores: Dict[str, float] = {}
    meta:   Dict[str, Dict]  = {}

    # Score vector results
    for rank, result in enumerate(vector_results, start=1):
        url = result.get("url", "")
        if not url:
            continue
        rrf = vector_weight * (1.0 / (RRF_K + rank))
        scores[url] = scores.get(url, 0.0) + rrf
        if url not in meta:
            meta[url] = {
                "url":          url,
                "title":        result.get("title", ""),
                "domain":       result.get("domain", _extract_domain(url)),
                "snippet":      result.get("text", "")[:300],
                "vector_score": result.get("_score", 0.0),
                "bm25_rank":    0.0,
                "in_vector":    True,
                "in_bm25":      False,
            }

    # Score BM25 results
    for rank, result in enumerate(bm25_results, start=1):
        url = result.get("url", "")
        if not url:
            continue
        rrf = bm25_weight * (1.0 / (RRF_K + rank))
        scores[url] = scores.get(url, 0.0) + rrf
        if url not in meta:
            meta[url] = {
                "url":          url,
                "title":        result.get("title", ""),
                "domain":       result.get("domain", _extract_domain(url)),
                "snippet":      result.get("snippet", ""),
                "vector_score": 0.0,
                "bm25_rank":    result.get("bm25_rank", 0.0),
                "in_vector":    False,
                "in_bm25":      True,
            }
        else:
            # URL appeared in both — enrich snippet from BM25 (it's better)
            meta[url]["snippet"]   = result.get("snippet", meta[url]["snippet"])
            meta[url]["bm25_rank"] = result.get("bm25_rank", 0.0)
            meta[url]["in_bm25"]   = True

    # Sort by combined RRF score
    ranked_urls = sorted(scores.keys(), key=lambda u: scores[u], reverse=True)

    results = []
    for url in ranked_urls[:top_k]:
        entry = meta[url].copy()
        entry["score"] = round(scores[url], 6)
        # Prefer longer snippet from BM25 if we have it
        if not entry["snippet"] and entry.get("vector_snippet"):
            entry["snippet"] = entry["vector_snippet"]
        results.append(entry)

    return results


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return ""
