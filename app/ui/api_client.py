# app/ui/api_client.py
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = 'http://localhost:8000'
_TIMEOUT = 60


class APIError(Exception):
    """Raised when the API returns a non-2xx status or is unreachable."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class APIClient:
    """HTTP client for the Enterprise Knowledge Assistant API.

    All methods return plain dicts matching the API response shape.
    Raises APIError on connection failures or non-2xx responses so callers
    can surface a clean error in the UI rather than an uncaught exception.

    Args:
        base_url: API base URL. Reads API_BASE_URL env var when None.
        session: Optional requests.Session to inject (used in tests).
    """

    def __init__(
        self,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._base = (base_url or os.environ.get('API_BASE_URL', _DEFAULT_BASE_URL)).rstrip('/')
        self._session = session or requests.Session()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def ask(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> dict:
        """POST /ask -- answer a question from the knowledge base.

        Args:
            query: User question string.
            history: Prior conversation turns as list of
                     {'query': str, 'answer': str} dicts, oldest first.
                     Only non-refusal turns should be included.

        Returns:
            AskResponse dict: answer, citations, confidence_band,
            confidence_percent, processing_time_ms, is_refusal.
        """
        payload: dict = {'query': query}
        if history:
            payload['history'] = history
        return self._post('/ask', json=payload)

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    def rebuild(self) -> dict:
        """POST /rebuild-index -- rebuild the vector index from all PDFs.

        Returns:
            RebuildResponse dict: total_chunks, documents, elapsed_ms, message.
        """
        return self._post('/rebuild-index')

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def health(self) -> dict:
        """GET /health -- shallow component health check.

        Returns:
            HealthResponse dict: status, vector_store, llm, timestamp.
        """
        return self._get('/health')

    def metrics(self) -> dict:
        """GET /metrics -- request counts and latency percentiles.

        Returns:
            MetricsResponse dict: ask_request_count, ask_p50_ms, etc.
        """
        return self._get('/metrics')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> dict:
        url = f'{self._base}{path}'
        try:
            resp = self._session.get(url, timeout=_TIMEOUT)
            self._raise_for_status(resp)
            return resp.json()
        except requests.exceptions.ConnectionError as exc:
            raise APIError(f'Cannot reach the API at {self._base}. Is the server running?') from exc
        except APIError:
            raise
        except Exception as exc:
            raise APIError(f'Unexpected error: {exc}') from exc

    def _post(self, path: str, **kwargs: object) -> dict:
        url = f'{self._base}{path}'
        try:
            resp = self._session.post(url, timeout=_TIMEOUT, **kwargs)
            self._raise_for_status(resp)
            return resp.json()
        except requests.exceptions.ConnectionError as exc:
            raise APIError(f'Cannot reach the API at {self._base}. Is the server running?') from exc
        except APIError:
            raise
        except Exception as exc:
            raise APIError(f'Unexpected error: {exc}') from exc

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if not resp.ok:
            try:
                detail = resp.json().get('message', resp.text)
            except Exception:
                detail = resp.text
            raise APIError(f'API error {resp.status_code}: {detail}', status_code=resp.status_code)
