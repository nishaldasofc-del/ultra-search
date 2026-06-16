"""
OpenRouter LLM Client — base class for all LLM calls
"""

import httpx
import json
from typing import Optional, List, Dict
from config import settings
import logging

logger = logging.getLogger(__name__)


class OpenRouterClient:
    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.fast_model
        self.api_key = settings.openrouter_api_key
        self.base_url = settings.openrouter_base_url

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

    async def complete(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Call the OpenRouter chat completions endpoint."""
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        payload: Dict = {
            "model": self.model,
            "messages": all_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ultrasearch.app",
            "X-Title": "Ultra Search Engine",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]

    async def complete_json(self, messages: List[Dict], system: Optional[str] = None, **kwargs) -> Dict:
        """Call and parse JSON response."""
        text = await self.complete(
            messages,
            system=system,
            response_format={"type": "json_object"},
            **kwargs,
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Strip markdown fences if present
            cleaned = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(cleaned)
