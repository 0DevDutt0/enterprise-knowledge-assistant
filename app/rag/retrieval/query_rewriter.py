# app/rag/retrieval/query_rewriter.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.rag.generation.llm_client import LLMClient

logger = logging.getLogger(__name__)


class QueryRewriter(ABC):
    """Abstract base class for query rewriting strategies.

    A rewriter takes a cleaned query string and returns a version that is
    more suitable for vector-store retrieval. Implementations may use an LLM,
    a rule-based system, or a no-op passthrough.
    """

    @abstractmethod
    def rewrite(self, query: str) -> str:
        """Return a retrieval-optimised version of the query.

        Args:
            query: Cleaned user query (control characters already stripped).

        Returns:
            Rewritten query string. Must never return an empty string;
            fall back to the original query on any failure.
        """


class PassthroughRewriter(QueryRewriter):
    """Returns the query unchanged.

    Used when query_rewriting_enabled=False so the pipeline has a consistent
    interface without branching on None.
    """

    def rewrite(self, query: str) -> str:
        """Return the query unchanged."""
        return query


class LLMQueryRewriter(QueryRewriter):
    """Rewrites queries using an LLM guided by a prompt template.

    The prompt instructs the model to resolve pronouns, expand acronyms, and
    convert vague requests into precise retrieval queries. Falls back to the
    original query on any LLM error so retrieval always proceeds.

    Args:
        llm_client: Shared LLM client instance (same one used by generation).
        template_path: Path to the query rewrite prompt markdown template.
    """

    def __init__(self, llm_client: LLMClient, template_path: str) -> None:
        self._llm = llm_client
        self._template = Path(template_path).read_text(encoding='utf-8')
        logger.info('llm_query_rewriter.init template_path=%s', template_path)

    def rewrite(self, query: str) -> str:
        """Call the LLM to rewrite the query, falling back to original on error.

        Args:
            query: Cleaned user query string.

        Returns:
            Rewritten query, or the original if the LLM call fails or returns
            an empty string.
        """
        prompt = self._template.format(query=query)
        try:
            raw = self._llm.complete(prompt)
            rewritten = raw.split('\n')[0].strip()
            if not rewritten:
                logger.warning('llm_query_rewriter.empty_response query_len=%d', len(query))
                return query
            if rewritten != query:
                logger.info(
                    'llm_query_rewriter.rewritten original=%r rewritten=%r',
                    query,
                    rewritten,
                )
            return rewritten
        except Exception as exc:
            logger.warning(
                'llm_query_rewriter.fallback query_len=%d error=%s', len(query), exc
            )
            return query
