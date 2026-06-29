"""LLM-based translation for job postings via OpenRouter."""

from __future__ import annotations

import logging

import httpx

from avalone_landing.config import settings

logger = logging.getLogger(__name__)


class OpenRouterTranslator:
    """Translate job-post texts using the OpenRouter chat-completions endpoint.

    Falls back to the original text when the API key is missing or the call fails.
    """

    _LANG_NAMES = {
        "ru": "Russian",
        "en": "English",
        "ko": "Korean",
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        cfg = settings()
        self.api_key = api_key or cfg.openrouter_api_key
        self.model = model or cfg.openrouter_model
        self.base_url = base_url or cfg.openrouter_base_url

    def translate(self, text: str, target_lang: str, source_lang: str = "en") -> str:
        """Return ``text`` translated into ``target_lang``."""
        if not text or not self.api_key:
            return text

        target_name = self._LANG_NAMES.get(target_lang, target_lang)
        source_name = self._LANG_NAMES.get(source_lang, source_lang)
        prompt = (
            f"Translate the following job posting from {source_name} to {target_name}. "
            "Preserve paragraphs and bullet structure. "
            "Return only the translation, with no extra commentary.\n\n"
            f"{text}"
        )

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://avalone.online",
                    "X-Title": "Avalone Work Aggregator",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenRouter translation failed: %s", exc)
            return text
