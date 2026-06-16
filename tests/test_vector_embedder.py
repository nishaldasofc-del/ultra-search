"""
Tests for vector.embedder — Embedder + chunk_text
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from vector.embedder import chunk_text, CHUNK_SIZE, CHUNK_OVERLAP


class TestChunkText:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("hello world", chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == "hello world"

    def test_long_text_multiple_chunks(self):
        words = ["word"] * 600
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        assert len(chunks) > 1

    def test_chunks_have_overlap(self):
        words = [str(i) for i in range(600)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        # Last word of chunk N should appear near start of chunk N+1
        last_words_of_first  = set(chunks[0].split()[-20:])
        first_words_of_second = set(chunks[1].split()[:20])
        assert last_words_of_first & first_words_of_second  # non-empty intersection

    def test_empty_text_returns_empty_list(self):
        assert chunk_text("") == []

    def test_chunk_size_respected(self):
        words = ["x"] * 1000
        chunks = chunk_text(" ".join(words), chunk_size=50, overlap=10)
        for c in chunks[:-1]:
            assert len(c.split()) == 50


class TestEmbedder:
    @pytest.mark.asyncio
    async def test_embed_returns_vector(self):
        fake_embedding = [0.1] * 1536

        with patch("vector.embedder.httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "data": [{"embedding": fake_embedding}]
            }
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_resp)
            ))
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"}):
                from vector.embedder import Embedder
                embedder = Embedder()
                embedder.api_key = "test-key"
                result = await embedder.embed("hello world")

        assert len(result) == 1536
        assert result[0] == 0.1

    @pytest.mark.asyncio
    async def test_embed_batch_returns_multiple(self):
        fake = [[0.1] * 1536, [0.2] * 1536]

        with patch("vector.embedder.httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "data": [{"embedding": e} for e in fake]
            }
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_resp)
            ))
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            from vector.embedder import Embedder
            embedder = Embedder()
            embedder.api_key = "test-key"
            results = await embedder.embed_batch(["text1", "text2"])

        assert len(results) == 2
        assert results[1][0] == 0.2
