# app/evaluation/runner.py
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.evaluation.metrics import (
    BenchmarkQuestion,
    MetricsSummary,
    QuestionResult,
    _citation_hits_expected,
    compute_all_metrics,
)

if TYPE_CHECKING:
    from app.ui.api_client import APIClient

logger = logging.getLogger(__name__)

_BENCHMARK_PATH = os.path.join(
    os.path.dirname(__file__), 'benchmarks', 'questions.json'
)


@dataclass
class EvalRun:
    """The complete output of one evaluation pass."""

    results: list[QuestionResult]
    summary: MetricsSummary
    timestamp: datetime
    total_elapsed_ms: float


def load_questions(path: str = _BENCHMARK_PATH) -> list[BenchmarkQuestion]:
    """Load benchmark questions from a JSON file.

    Args:
        path: Absolute or relative path to a questions JSON file.

    Returns:
        List of BenchmarkQuestion instances.
    """
    with open(path, 'r', encoding='utf-8') as fh:
        raw = json.load(fh)
    return [
        BenchmarkQuestion(
            id=item['id'],
            question=item['question'],
            expected_source_documents=item.get('expected_source_documents', []),
            expected_pages=item.get('expected_pages', []),
            answer_must_contain=item.get('answer_must_contain', []),
            answer_must_not_contain=item.get('answer_must_not_contain', []),
            category=item['category'],
        )
        for item in raw
    ]


class EvalRunner:
    """Runs the benchmark question set against the live API and collects results.

    Args:
        client: An APIClient instance pointing at the running API.
        questions: Benchmark questions to evaluate; loaded from the default
            benchmark file when omitted.
    """

    def __init__(
        self,
        client: APIClient,
        questions: list[BenchmarkQuestion] | None = None,
    ) -> None:
        self._client = client
        self._questions = questions or load_questions()

    def run(self) -> EvalRun:
        """Execute every question and return a completed EvalRun.

        Returns:
            EvalRun with per-question results and aggregate metrics.
        """
        start_wall = time.monotonic()
        results: list[QuestionResult] = []

        for q in self._questions:
            result = self._run_one(q)
            results.append(result)
            logger.info(
                'eval question %s done is_refusal=%s hit=%s',
                q.id,
                result.is_refusal,
                result.retrieval_hit,
            )

        summary = compute_all_metrics(results)
        total_ms = (time.monotonic() - start_wall) * 1000.0

        return EvalRun(
            results=results,
            summary=summary,
            timestamp=datetime.now(timezone.utc),
            total_elapsed_ms=total_ms,
        )

    def _run_one(self, question: BenchmarkQuestion) -> QuestionResult:
        """Ask one question and build a QuestionResult from the API response."""
        try:
            response = self._client.ask(question.question)
        except Exception as exc:
            logger.warning('eval question %s failed: %s', question.id, exc)
            return QuestionResult(
                question=question,
                answer_text='',
                citations=[],
                is_refusal=True,
                confidence_band='Low',
                confidence_percent=0.0,
                processing_time_ms=0.0,
                retrieval_hit=False,
            )

        citations: list[dict] = response.get('citations', [])
        retrieval_hit = any(
            _citation_hits_expected(c, question) for c in citations
        )

        return QuestionResult(
            question=question,
            answer_text=response.get('answer', ''),
            citations=citations,
            is_refusal=response.get('is_refusal', False),
            confidence_band=response.get('confidence_band', 'Low'),
            confidence_percent=response.get('confidence_percent', 0.0),
            processing_time_ms=response.get('processing_time_ms', 0.0),
            retrieval_hit=retrieval_hit,
        )


def write_report(run: EvalRun, output_dir: str) -> str:
    """Write a markdown evaluation report and return its file path.

    Args:
        run: A completed EvalRun.
        output_dir: Directory where the report is written; created if absent.

    Returns:
        Absolute path of the written report file.
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = run.timestamp.strftime('%Y-%m-%d-%H%M')
    filename = f'{ts}.md'
    path = os.path.join(output_dir, filename)

    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(_render_report(run))

    return path


def _render_report(run: EvalRun) -> str:
    """Render the EvalRun as a markdown string."""
    s = run.summary
    ts_str = run.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    lines: list[str] = []

    lines += [
        '# Evaluation Report',
        '',
        f'**Run timestamp:** {ts_str}',
        f'**Total elapsed:** {run.total_elapsed_ms:.0f} ms',
        f'**Questions:** {s.total_questions}',
        '',
        '---',
        '',
        '## Aggregate Metrics',
        '',
        '| Metric | Value |',
        '|--------|-------|',
        f'| Retrieval Precision@5 | {s.retrieval_precision_at_5:.1%} |',
        f'| Citation Accuracy | {s.citation_accuracy:.1%} |',
        f'| Hallucination Rate | {s.hallucination_rate:.1%} |',
        f'| Refusal Rate (unsupported) | {s.refusal_rate_on_unsupported:.1%} |',
        f'| Latency p50 | {s.latency_p50_ms:.0f} ms |',
        f'| Latency p95 | {s.latency_p95_ms:.0f} ms |',
        f'| Answered | {s.answered} / {s.total_questions} |',
        f'| Refused | {s.refused} / {s.total_questions} |',
        '',
        '---',
        '',
        '## Results by Category',
        '',
        '| Category | Total | Answered | Refused | Retrieval Hit Rate |',
        '|----------|-------|----------|---------|-------------------|',
    ]

    for cat, stats in sorted(s.by_category.items()):
        hit_rate = stats['retrieval_hit_rate']
        assert isinstance(hit_rate, float)
        lines.append(
            f'| {cat} | {stats["total"]} | {stats["answered"]} |'
            f' {stats["refused"]} | {hit_rate:.1%} |'
        )

    lines += [
        '',
        '---',
        '',
        '## Per-Question Results',
        '',
        '| ID | Category | Refusal | Hit | Confidence | Time (ms) |',
        '|----|----------|---------|-----|-----------|----------|',
    ]

    for r in run.results:
        refusal_mark = 'Yes' if r.is_refusal else 'No'
        hit_mark = 'Yes' if r.retrieval_hit else 'No'
        lines.append(
            f'| {r.question.id} | {r.question.category} | {refusal_mark} |'
            f' {hit_mark} | {r.confidence_band} {r.confidence_percent:.1f}% |'
            f' {r.processing_time_ms:.0f} |'
        )

    lines += [
        '',
        '---',
        '',
        '## Per-Question Detail',
        '',
    ]

    for r in run.results:
        lines += [
            f'### {r.question.id} — {r.question.category}',
            '',
            f'**Question:** {r.question.question}',
            '',
            f'**Answer:** {r.answer_text[:500]}{"..." if len(r.answer_text) > 500 else ""}',
            '',
            f'**Refusal:** {"Yes" if r.is_refusal else "No"}  '
            f'**Retrieval hit:** {"Yes" if r.retrieval_hit else "No"}  '
            f'**Confidence:** {r.confidence_band} {r.confidence_percent:.1f}%  '
            f'**Latency:** {r.processing_time_ms:.0f} ms',
            '',
        ]
        if r.citations:
            lines.append('**Citations:**')
            for c in r.citations:
                lines.append(
                    f'- {c.get("document", "?")} p.{c.get("page", "?")} '
                    f'({c.get("section", "")})'
                )
            lines.append('')

    lines.append('*Generated by EvalRunner*')
    return '\n'.join(lines)
