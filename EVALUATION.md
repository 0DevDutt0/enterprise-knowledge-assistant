# EVALUATION.md — How the system is measured

This document defines what "good" means for this project. The evaluation
suite must be runnable and reproducible. The numbers below are reported in
the final eval report committed under `docs/eval-reports/`.

---

## 1. Why evaluate

A RAG system that "feels right" in a demo can still be a hallucination
machine in practice. Without a benchmark suite, you cannot answer:

- Did refactor X make retrieval worse?
- Does the system fabricate when it should refuse?
- Which kinds of question fail most?

The eval suite is a regression net, not a publishable benchmark. It exists
to catch silent drift.

---

## 2. Benchmark set

Location: `app/evaluation/benchmarks/questions.json`.

Shape:
```json
[
  {
    "id": "q001",
    "question": "What is the maximum supported batch size for the API?",
    "expected_source_documents": ["api-reference.pdf"],
    "expected_pages": [12, 13],
    "answer_must_contain": ["batch", "100"],
    "answer_must_not_contain": [],
    "category": "factual_lookup"
  }
]
```

Minimum coverage:
- At least 15 questions.
- At least 3 source documents.
- Categories represented: `factual_lookup`, `multi_hop`, `unsupported`
  (answer is intentionally NOT in the corpus — system must refuse),
  `numeric`, `definition`.

---

## 3. Metrics

### Retrieval precision@5

Fraction of questions where at least one of the top 5 reranked chunks comes
from an expected source document on an expected page.

Why: confirms the retriever is surfacing the right region of the corpus.
Generation can only be as good as retrieval.

### Citation accuracy

Fraction of answers whose cited chunks actually contain the substring(s)
listed in `answer_must_contain` (case-insensitive). Penalises citation
hallucination — the model citing a chunk that does not support the answer.

### Hallucination rate

A question counts as a hallucination if either:
- The question is in the `unsupported` category and the system produced a
  non-refusal answer.
- For any category, the answer contains any string in
  `answer_must_not_contain`.

Target: < 5%.

### Refusal rate on unsupported

Fraction of `unsupported` questions where the system returned the canonical
"information not found" response. Should be 100%.

### Latency

For each phase, report p50 and p95 over the full run:
- Retrieval (embed + search)
- Rerank
- Generation (LLM round trip)
- End-to-end /ask

### Index health

Reported once per run, not per question:
- Number of documents indexed
- Number of chunks
- Mean chunk size
- Index file size on disk

---

## 4. How to run

```
python scripts/run_eval.py
```

The script:
1. Confirms the index is loaded (rebuilds if `--rebuild`).
2. Walks the benchmark set serially (concurrency would skew Groq latency).
3. Computes metrics.
4. Writes a markdown report to `docs/eval-reports/YYYY-MM-DD-HHMM.md`.
5. Prints a one-line summary suitable for commit messages.

---

## 5. Report format

Each eval report contains:
- Run metadata (timestamp, git SHA, settings dump).
- Aggregate metrics table.
- Per-question breakdown with pass/fail and the actual answer.
- Latency histograms.
- Diffs against the previous report if one exists.

---

## 6. Interpreting results

- **Retrieval precision low, citation accuracy high:** chunking is splitting
  evidence; consider larger chunks or different element handling.
- **Retrieval precision high, citation accuracy low:** prompt is not
  attributing well; tighten the citation instruction.
- **Hallucination rate non-zero on `unsupported`:** confidence floor is too
  low, or the LLM is overriding the system prompt — investigate both.
- **Generation latency dominates:** expected, since Groq is the network
  hop. Retrieval+rerank should sit well under 500ms on CPU for a
  small index.

---

## 7. Caveats

- The benchmark is small and authored by the project owner. It is not a
  substitute for a real labeled dataset.
- "Answer must contain" is a weak proxy for correctness; it catches
  catastrophic failures but not subtle paraphrases. Manual spot-checks
  remain necessary for shipping decisions.
- Latency numbers depend on machine and network; compare runs from the
  same environment.
