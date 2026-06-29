# app/rag/generation/llm_client.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM completion clients.

    A single-turn completion interface: send a fully-formed prompt string,
    receive a string response. Retry and timeout semantics are left to
    concrete implementations.
    """

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Send prompt and return the model's text response.

        Args:
            prompt: Complete prompt string (system + context + question).

        Returns:
            Model response as a plain string.

        Raises:
            LLMError: On non-retryable API errors or exhausted retries.
        """


class GroqClient(LLMClient):
    """Groq API client backed by the official groq-python SDK.

    Wraps the chat completion endpoint with timeout enforcement and
    transparent retries on transient server errors. Rate-limit errors
    are NOT retried; they propagate as LLMError so the caller can
    surface a 429-style response to the user.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: int,
        max_retries: int,
    ) -> None:
        from groq import Groq
        self._model = model
        self._client = Groq(
            api_key=api_key,
            timeout=float(timeout),
            max_retries=max_retries,
        )
        logger.info('groq_client.init model=%s timeout=%ds', model, timeout)

    def complete(self, prompt: str) -> str:
        """Submit prompt to Groq chat completions and return the answer text.

        Args:
            prompt: Fully assembled prompt string.

        Returns:
            Response content string from the model.

        Raises:
            LLMError: On rate limit or non-retryable API errors.
        """
        from groq import RateLimitError
        from app.middleware.errors import LLMError

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{'role': 'user', 'content': prompt}],
            )
            text: str = response.choices[0].message.content or ''
            logger.debug(
                'groq_client.complete model=%s response_chars=%d',
                self._model,
                len(text),
            )
            return text.strip()
        except RateLimitError as exc:
            logger.warning('groq_client.rate_limited model=%s', self._model)
            raise LLMError(f'Groq rate limit exceeded: {exc}') from exc
        except Exception as exc:
            logger.error('groq_client.error model=%s error=%s', self._model, exc)
            raise LLMError(f'Groq API error: {exc}') from exc
