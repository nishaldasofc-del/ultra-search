"""
Deduplicator — removes exact and near-duplicate pages
Uses URL normalization + content fingerprinting (SimHash-lite)
"""

import hashlib
import re
from typing import List, Dict
from urllib.parse import urlparse, urlunparse


def _normalize_url(url: str) -> str:
    """Strip trailing slashes, fragments, common tracking params."""
    parsed = urlparse(url)
    # Remove fragment
    cleaned = parsed._replace(fragment="")
    path = cleaned.path.rstrip("/") or "/"
    cleaned = cleaned._replace(path=path)
    return urlunparse(cleaned).lower()


def _fingerprint(text: str, shingle_size: int = 4) -> set:
    """Produce a set of shingle hashes for near-dup detection."""
    words = re.findall(r"\w+", text.lower())
    shingles = set()
    for i in range(len(words) - shingle_size + 1):
        shingle = " ".join(words[i : i + shingle_size])
        shingles.add(hashlib.md5(shingle.encode()).hexdigest()[:8])
    return shingles


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Deduplicator:
    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold

    def deduplicate(self, results: List[Dict]) -> List[Dict]:
        seen_urls: set = set()
        seen_fingerprints: List[set] = []
        unique: List[Dict] = []

        for r in results:
            url = _normalize_url(r.get("url", ""))
            if url in seen_urls:
                continue
            seen_urls.add(url)

            content = r.get("content") or r.get("snippet", "")
            fp = _fingerprint(content)

            # Check near-dup
            is_dup = False
            for existing_fp in seen_fingerprints:
                if _jaccard(fp, existing_fp) >= self.threshold:
                    is_dup = True
                    break

            if not is_dup:
                seen_fingerprints.append(fp)
                unique.append(r)

        return unique
