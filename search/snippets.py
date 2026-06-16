"""
Snippets — generate clean result snippets from page content.
Used when BM25 snippet is unavailable (vector-only results).
Finds the sentence in the content most relevant to the query.
"""

import re
from typing import List, Optional


def extract_snippet(
    content: str,
    query: str,
    max_chars: int = 280,
) -> str:
    """
    Find the best snippet from content for a given query.
    Strategy: score each sentence by query-term overlap, return the best.
    """
    if not content:
        return ""

    query_terms = set(_tokenize(query))
    sentences   = _split_sentences(content)

    if not sentences:
        return content[:max_chars]

    # Score each sentence by term overlap
    best_score    = -1
    best_sentence = sentences[0]

    for sentence in sentences:
        tokens = set(_tokenize(sentence))
        score  = len(query_terms & tokens) / (len(query_terms) + 1)
        if score > best_score:
            best_score    = score
            best_sentence = sentence

    # If no overlap at all, return start of content
    if best_score == 0:
        return content[:max_chars].rstrip() + "…"

    # Try to include neighbouring sentence for context
    idx = sentences.index(best_sentence)
    parts = [best_sentence]
    if idx + 1 < len(sentences):
        parts.append(sentences[idx + 1])

    snippet = " ".join(parts)
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip() + "…"

    return snippet


def _tokenize(text: str) -> List[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if len(s.strip()) > 20]
