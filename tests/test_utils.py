"""
Tests for utility modules: urls, text, retry
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

# ── url utils ─────────────────────────────────────────────────────────────────
from utils.urls import normalize, domain, is_valid, same_domain, make_absolute


class TestNormalize:
    def test_strips_trailing_slash(self):
        assert normalize("https://example.com/page/") == "https://example.com/page"

    def test_lowercases_scheme_and_host(self):
        assert normalize("HTTPS://EXAMPLE.COM/Path") == "https://example.com/Path"

    def test_strips_fragment(self):
        assert normalize("https://example.com/page#section") == "https://example.com/page"

    def test_preserves_query_string(self):
        result = normalize("https://example.com/search?q=python")
        assert "q=python" in result

    def test_idempotent(self):
        url = "https://example.com/path"
        assert normalize(normalize(url)) == normalize(url)


class TestDomain:
    def test_extracts_domain(self):
        assert domain("https://www.example.com/page") == "www.example.com"

    def test_lowercases(self):
        assert domain("https://EXAMPLE.COM") == "example.com"


class TestIsValid:
    def test_https_valid(self):       assert is_valid("https://example.com") is True
    def test_http_valid(self):        assert is_valid("http://example.com") is True
    def test_no_scheme_invalid(self): assert is_valid("example.com") is False
    def test_ftp_invalid(self):       assert is_valid("ftp://example.com") is False
    def test_empty_invalid(self):     assert is_valid("") is False


class TestSameDomain:
    def test_same(self):             assert same_domain("https://a.com/p1", "https://a.com/p2") is True
    def test_different(self):        assert same_domain("https://a.com", "https://b.com") is False
    def test_subdomain_different(self): assert same_domain("https://a.com", "https://www.a.com") is False


class TestMakeAbsolute:
    def test_relative_path(self):
        assert make_absolute("https://example.com/docs/", "guide.html") == "https://example.com/docs/guide.html"

    def test_absolute_href_unchanged(self):
        assert make_absolute("https://example.com", "https://other.com/page") == "https://other.com/page"


# ── text utils ────────────────────────────────────────────────────────────────
from utils.text import word_count, truncate, extract_sentences, clean_whitespace, strip_html


class TestWordCount:
    def test_counts_words(self):  assert word_count("hello world foo") == 3
    def test_empty(self):         assert word_count("") == 0


class TestTruncate:
    def test_short_unchanged(self):
        assert truncate("hello world", max_words=10) == "hello world"

    def test_long_truncated(self):
        text = " ".join(["word"] * 50)
        result = truncate(text, max_words=10)
        assert result.endswith("…")
        assert len(result.split()) <= 11  # 10 words + "…"


class TestExtractSentences:
    def test_splits_sentences(self):
        sents = extract_sentences("Hello world. How are you? Fine!")
        assert len(sents) == 3

    def test_empty_string(self):
        assert extract_sentences("") == []


class TestCleanWhitespace:
    def test_collapses_spaces(self):
        assert clean_whitespace("hello   world") == "hello world"

    def test_strips_leading_trailing(self):
        assert clean_whitespace("  hi  ") == "hi"


class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_no_tags_unchanged(self):
        assert strip_html("plain text") == "plain text"


# ── retry decorator ───────────────────────────────────────────────────────────
from utils.retry import async_retry


class TestAsyncRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        call_count = 0

        @async_retry(max_attempts=3)
        async def ok():
            nonlocal call_count
            call_count += 1
            return "done"

        result = await ok()
        assert result == "done"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        attempts = []

        @async_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("not yet")
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert len(attempts) == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        @async_retry(max_attempts=2, delay=0.01, exceptions=(RuntimeError,))
        async def always_fails():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await always_fails()

    @pytest.mark.asyncio
    async def test_unretried_exception_propagates_immediately(self):
        """Exceptions not in the tuple should NOT be retried."""
        calls = []

        @async_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def type_error():
            calls.append(1)
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            await type_error()

        assert len(calls) == 1   # no retry
