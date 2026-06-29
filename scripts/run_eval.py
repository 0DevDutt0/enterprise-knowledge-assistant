# scripts/run_eval.py
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.evaluation.runner import EvalRunner, load_questions, write_report
from app.ui.api_client import APIClient, APIError

_REPORT_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'docs', 'eval-reports'
)

_MENU = """
Enterprise Knowledge Assistant -- Evaluation
============================================
1. Run evaluation (API must already be running)
2. List benchmark questions
3. Check API health before running
q. Quit

Choice: """


def _run_evaluation(client: APIClient) -> None:
    """Run the full benchmark suite and write a report."""
    print('\nLoading benchmark questions...')
    questions = load_questions()
    print(f'Loaded {len(questions)} questions.')
    print('Running evaluation (this may take a few minutes)...\n')

    runner = EvalRunner(client=client, questions=questions)
    run = runner.run()

    s = run.summary
    print('\n--- Aggregate Results ---')
    print(f'  Questions:              {s.total_questions}')
    print(f'  Answered:               {s.answered}')
    print(f'  Refused:                {s.refused}')
    print(f'  Retrieval Precision@5:  {s.retrieval_precision_at_5:.1%}')
    print(f'  Citation Accuracy:      {s.citation_accuracy:.1%}')
    print(f'  Hallucination Rate:     {s.hallucination_rate:.1%}')
    print(f'  Refusal (unsupported):  {s.refusal_rate_on_unsupported:.1%}')
    print(f'  Latency p50:            {s.latency_p50_ms:.0f} ms')
    print(f'  Latency p95:            {s.latency_p95_ms:.0f} ms')
    print(f'  Total elapsed:          {run.total_elapsed_ms:.0f} ms')

    report_path = write_report(run, _REPORT_DIR)
    print(f'\nReport written to: {report_path}')


def _list_questions() -> None:
    """Print all benchmark questions with their IDs and categories."""
    questions = load_questions()
    print(f'\n{len(questions)} benchmark questions:\n')
    for q in questions:
        tag = f'[{q.category}]'
        print(f'  {q.id}  {tag:<20}  {q.question}')
    print()


def _check_health(client: APIClient) -> None:
    """Call GET /health and display the result."""
    try:
        result = client.health()
        overall = result.get('status', 'unknown')
        vs = result.get('vector_store', {}).get('status', 'unknown')
        llm = result.get('llm', {}).get('status', 'unknown')
        print(f'\n  Overall:      {overall}')
        print(f'  Vector store: {vs}')
        print(f'  LLM:          {llm}')
    except APIError as exc:
        print(f'\n  Health check failed: {exc}')
    print()


def main() -> None:
    """Interactive evaluation CLI entry point."""
    base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000')
    print(f'\nConnecting to API at: {base_url}')
    client = APIClient(base_url=base_url)

    while True:
        choice = input(_MENU).strip().lower()

        if choice == '1':
            _run_evaluation(client)
        elif choice == '2':
            _list_questions()
        elif choice == '3':
            _check_health(client)
        elif choice == 'q':
            print('Goodbye.')
            break
        else:
            print('Invalid choice. Enter 1, 2, 3, or q.')


if __name__ == '__main__':
    main()
