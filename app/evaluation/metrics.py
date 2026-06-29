# app/evaluation/metrics.py
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class BenchmarkQuestion:
    """A single evaluation question with expected retrieval and answer metadata."""

    id: str
    question: str
    expected_source_documents: list[str]
    expected_pages: list[int]
    answer_must_contain: list[str]
    answer_must_not_contain: list[str]
    category: str


@dataclass
class QuestionResult:
    """The outcome of asking one BenchmarkQuestion against the live system."""

    question: BenchmarkQuestion
    answer_text: str
    citations: list[dict]
    is_refusal: bool
    confidence_band: str
    confidence_percent: float
    processing_time_ms: float
    retrieval_hit: bool


@dataclass
class MetricsSummary:
    """Aggregate metrics computed over a full evaluation run."""

    retrieval_precision_at_5: float
    citation_accuracy: float
    hallucination_rate: float
    refusal_rate_on_unsupported: float
    latency_p50_ms: float
    latency_p95_ms: float
    total_questions: int
    answered: int
    refused: int
    by_category: dict[str, dict[str, object]] = field(default_factory=dict)


def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile of *data* (0-100 scale).

    Uses nearest-rank method. Returns 0.0 for empty input.
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = max(0, math.ceil(p / 100.0 * len(sorted_data)) - 1)
    return sorted_data[idx]


def _citation_hits_expected(citation: dict, question: BenchmarkQuestion) -> bool:
    """Return True if this citation matches the question's expected source+page."""
    doc_match = citation.get('document', '') in question.expected_source_documents
    if not question.expected_pages:
        return doc_match
    page_match = citation.get('page', -1) in question.expected_pages
    return doc_match and page_match


def _answer_contains_required(result: QuestionResult) -> bool:
    """Return True if the answer text contains all must-contain terms (case-insensitive)."""
    if not result.question.answer_must_contain:
        return True
    lower = result.answer_text.lower()
    return all(term.lower() in lower for term in result.question.answer_must_contain)


def _answer_contains_forbidden(result: QuestionResult) -> bool:
    """Return True if the answer text contains any must-not-contain term (case-sensitive)."""
    if not result.question.answer_must_not_contain:
        return False
    return any(term in result.answer_text for term in result.question.answer_must_not_contain)


def retrieval_precision_at_5(results: list[QuestionResult]) -> float:
    """Fraction of questions with at least one citation from the expected source/page.

    Unsupported questions (empty expected_source_documents) are excluded from
    the denominator. Returns 0.0 when no supported questions exist.
    """
    supported = [r for r in results if r.question.expected_source_documents]
    if not supported:
        return 0.0
    hits = sum(1 for r in supported if r.retrieval_hit)
    return hits / len(supported)


def citation_accuracy(results: list[QuestionResult]) -> float:
    """Fraction of non-refusal answers whose text contains all must-contain terms.

    Treats a refusal on a supported question as a miss. Unsupported questions
    with no must-contain terms are excluded from the denominator.
    """
    eligible = [
        r for r in results
        if r.question.answer_must_contain and not r.is_refusal
    ]
    if not eligible:
        return 0.0
    correct = sum(1 for r in eligible if _answer_contains_required(r))
    return correct / len(eligible)


def hallucination_rate(results: list[QuestionResult]) -> float:
    """Fraction of questions where the answer contains a forbidden substring.

    Refusals cannot hallucinate (they return the canonical message). Only
    non-refusal answers for questions that specify answer_must_not_contain
    are included in the denominator.
    """
    eligible = [
        r for r in results
        if r.question.answer_must_not_contain and not r.is_refusal
    ]
    if not eligible:
        return 0.0
    hallucinated = sum(1 for r in eligible if _answer_contains_forbidden(r))
    return hallucinated / len(eligible)


def refusal_rate_on_unsupported(results: list[QuestionResult]) -> float:
    """Fraction of unsupported questions that correctly produced a refusal.

    Returns 0.0 when there are no unsupported questions.
    """
    unsupported = [r for r in results if r.question.category == 'unsupported']
    if not unsupported:
        return 0.0
    refused = sum(1 for r in unsupported if r.is_refusal)
    return refused / len(unsupported)


def compute_all_metrics(results: list[QuestionResult]) -> MetricsSummary:
    """Compute all metrics from a completed list of QuestionResults."""
    latencies = [r.processing_time_ms for r in results]
    answered = sum(1 for r in results if not r.is_refusal)
    refused = sum(1 for r in results if r.is_refusal)

    categories: set[str] = {r.question.category for r in results}
    by_category: dict[str, dict[str, object]] = {}
    for cat in sorted(categories):
        cat_results = [r for r in results if r.question.category == cat]
        cat_refused = sum(1 for r in cat_results if r.is_refusal)
        by_category[cat] = {
            'total': len(cat_results),
            'answered': len(cat_results) - cat_refused,
            'refused': cat_refused,
            'retrieval_hit_rate': (
                sum(1 for r in cat_results if r.retrieval_hit) / len(cat_results)
                if cat_results else 0.0
            ),
        }

    return MetricsSummary(
        retrieval_precision_at_5=retrieval_precision_at_5(results),
        citation_accuracy=citation_accuracy(results),
        hallucination_rate=hallucination_rate(results),
        refusal_rate_on_unsupported=refusal_rate_on_unsupported(results),
        latency_p50_ms=_percentile(latencies, 50),
        latency_p95_ms=_percentile(latencies, 95),
        total_questions=len(results),
        answered=answered,
        refused=refused,
        by_category=by_category,
    )
