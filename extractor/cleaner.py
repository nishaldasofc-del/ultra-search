"""
Content Cleaner — normalises extracted text before indexing.
Removes noise, collapses whitespace, strips boilerplate patterns.
"""

import re
from typing import Optional


# Common boilerplate phrases to strip (case-insensitive)
_BOILERPLATE = re.compile(
    r"(cookie policy|accept cookies|subscribe to our newsletter"
    r"|all rights reserved|terms of (use|service)|privacy policy"
    r"|skip to (main )?content|share this (article|page|post)"
    r"|follow us on|sign up for|©\s*\d{4})",
    re.IGNORECASE,
)

_MULTI_SPACE   = re.compile(r" {2,}")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_LONE_CHARS    = re.compile(r"(?<!\w).\s+(?!\w)")  # single scattered chars


class ContentCleaner:
    def clean(self, text: str) -> str:
        if not text:
            return ""

        # Remove boilerplate patterns
        text = _BOILERPLATE.sub(" ", text)

        # Collapse excessive whitespace
        text = text.replace("\t", " ")
        text = _MULTI_SPACE.sub(" ", text)
        text = _MULTI_NEWLINE.sub("\n\n", text)

        # Strip leading/trailing
        text = text.strip()

        # Hard cap at 50k chars (prevents giant pages from blowing up embedding batches)
        if len(text) > 50_000:
            text = text[:50_000]

        return text
