"""
Content Parser — extracts clean structured data from raw HTML.
Pulls title, main content, meta description, og:image, outlinks, lang.
Uses readability-lxml for main content extraction (like Firefox Reader Mode).
"""

from typing import Dict, Optional
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class ContentParser:
    def parse(self, html: str, url: str) -> Dict:
        """
        Parse raw HTML into structured content dict:
          { title, content, description, image, lang, outlinks }
        """
        try:
            return self._parse_readability(html, url)
        except Exception as e:
            logger.debug(f"Readability failed for {url}: {e}, falling back to BS4")
            return self._parse_bs4(html, url)

    def _parse_readability(self, html: str, url: str) -> Dict:
        from readability import Document
        doc   = Document(html)
        title = doc.title() or ""
        # readability returns simplified HTML — strip to plain text
        soup  = BeautifulSoup(doc.summary(), "html.parser")
        content = soup.get_text(separator=" ", strip=True)

        # Get lang, description, and image from raw HTML (readability strips <head>)
        raw_soup    = BeautifulSoup(html, "html.parser")
        description = self._extract_meta(raw_soup)
        image       = self._extract_image(raw_soup)
        lang        = self._extract_lang(raw_soup)

        return {
            "title":       title.strip(),
            "content":     content,
            "description": description,
            "image":       image,
            "lang":        lang,
            "outlinks":    [],   # spider handles link extraction
        }

    def _parse_bs4(self, html: str, url: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "noscript", "iframe"]):
            tag.decompose()

        title = ""
        if soup.title:
            title = soup.title.string or ""

        # Try <main>, <article>, <body> in order
        for selector in ["main", "article", '[role="main"]', "body"]:
            el = soup.select_one(selector)
            if el:
                content = el.get_text(separator=" ", strip=True)
                break
        else:
            content = soup.get_text(separator=" ", strip=True)

        return {
            "title":       title.strip(),
            "content":     content,
            "description": self._extract_meta(soup),
            "image":       self._extract_image(soup),
            "lang":        self._extract_lang(soup),
            "outlinks":    [],
        }

    def _extract_meta(self, soup: BeautifulSoup) -> str:
        for attr in [{"name": "description"}, {"property": "og:description"}]:
            tag = soup.find("meta", attrs=attr)
            if tag and tag.get("content"):
                return tag["content"].strip()
        return ""

    def _extract_image(self, soup: BeautifulSoup) -> str:
        """
        Return the best available thumbnail URL for this page.

        Checks, in priority order:
          1. <meta property="og:image" content="...">   (Open Graph — most reliable)
          2. <meta name="twitter:image" content="...">  (Twitter Card — good fallback)

        Both tags live in <head> and are always present in the raw HTML,
        which is why this method must be called before readability strips the
        document down to body content.

        Returns an empty string if neither tag is found.
        """
        for attrs in [{"property": "og:image"}, {"name": "twitter:image"}]:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                return tag["content"].strip()
        return ""

    def _extract_lang(self, soup: BeautifulSoup) -> str:
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            return html_tag["lang"][:5]
        return "en"
