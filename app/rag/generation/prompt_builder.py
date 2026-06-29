# app/rag/generation/prompt_builder.py
from __future__ import annotations

import logging
from pathlib import Path

from app.models.conversation import ConversationTurn
from app.models.retrieval import RerankedResult

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Assembles the final LLM prompt from a query, reranked context, and history.

    Reads the system prompt template from disk once at construction time.
    Context is formatted as a numbered list of sourced passages and truncated
    to stay within the configured character budget.

    If the template contains a ``{history}`` placeholder, prior conversation
    turns are injected. Templates without this placeholder are unaffected
    (backward-compatible with minimal test templates).
    """

    def __init__(
        self,
        template_path: str,
        max_context_chars: int,
        max_history_turns: int = 5,
    ) -> None:
        self._template = Path(template_path).read_text(encoding='utf-8')
        self._max_context_chars = max_context_chars
        self._max_history_turns = max_history_turns

    def build(
        self,
        query: str,
        results: list[RerankedResult],
        history: list[ConversationTurn] | None = None,
    ) -> str:
        """Build the full LLM prompt for a query with its reranked context.

        Args:
            query: Cleaned user query string.
            results: Reranked retrieval results, sorted by relevance descending.
            history: Prior conversation turns (oldest first). Only the last
                     ``max_history_turns`` are injected; excess turns are dropped.

        Returns:
            Formatted prompt string ready to send to the LLM.
        """
        context_block = self._build_context(results)

        if '{history}' in self._template:
            history_block = self._build_history(history)
            prompt = self._template.format(
                context=context_block,
                question=query,
                history=history_block,
            )
        else:
            prompt = self._template.format(context=context_block, question=query)

        logger.debug(
            'prompt_builder.build context_chars=%d total_chars=%d',
            len(context_block),
            len(prompt),
        )
        return prompt

    def _build_context(self, results: list[RerankedResult]) -> str:
        """Format reranked chunks into a numbered context block.

        Chunks are included in reranked order. Addition stops when the next
        chunk would push the accumulated context over max_context_chars.
        At least one chunk is always included (even if oversized) so the LLM
        has something to work with.
        """
        if not results:
            return '(No relevant passages found.)'

        blocks: list[str] = []
        total_chars = 0

        for i, result in enumerate(results, start=1):
            meta = result.chunk.metadata
            header = (
                f'[{i}] Source: {meta.document} | Page: {meta.page}'
                + (f' | Section: {meta.section}' if meta.section else '')
            )
            block = f'{header}\n{"-" * 4}\n{result.chunk.text}'

            if blocks and total_chars + len(block) > self._max_context_chars:
                logger.debug(
                    'prompt_builder.truncated at chunk %d of %d', i - 1, len(results)
                )
                break

            blocks.append(block)
            total_chars += len(block)

        return '\n\n'.join(blocks)

    def _build_history(self, history: list[ConversationTurn] | None) -> str:
        """Format prior conversation turns into a readable block.

        Only the last ``max_history_turns`` turns are included. Oldest turns
        within that window appear first so the LLM sees them in chronological order.
        """
        if not history or self._max_history_turns == 0:
            return '(None)'

        turns = history[-self._max_history_turns:]
        lines: list[str] = []
        for turn in turns:
            lines.append(f'User: {turn.query}')
            lines.append(f'Assistant: {turn.answer}')
        return '\n'.join(lines)
