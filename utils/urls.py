"""
URL utilities — normalization, domain extraction, validation
"""

from urllib.parse import urlparse, urljoin, urlunparse
import re


def normalize(url: str) -> str:
    """Lowercase scheme+host, strip fragment, strip trailing slash."""
    p = urlparse(url.strip())
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, p.params, p.query, ""))


def domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def is_valid(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def same_domain(url_a: str, url_b: str) -> bool:
    return domain(url_a) == domain(url_b)


def make_absolute(base: str, href: str) -> str:
    return urljoin(base, href)
