"""
Text utilities — tokenization helpers, truncation, chunking
"""

import re
from typing import List


def word_count(text: str) -> int:
    return len(text.split())


def truncate(text: str, max_words: int = 300) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def extract_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def clean_whitespace(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text)
