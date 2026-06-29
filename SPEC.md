# SPEC.md -- Assignment Requirements (Acceptance Checklist)

This document distills the original assignment prompt into a flat, verifiable
checklist. Every item below must be implemented and demonstrably working
before the project is considered complete.

---

## Functional requirements

### Ingestion
- [x] Upload PDFs through the Streamlit UI.
- [x] Detect whether each PDF is digital (has selectable text) or scanned.
- [x] Digital PDFs: extract via PyMuPDF.
- [x] Scanned PDFs: fall back to Tesseract OCR.
- [x] OCR is only triggered when PyMuPDF returns no selectable text -- never
      pre-emptively.
- [x] Extracted output conforms to the unified `DocumentElement` model
      (heading, paragraph, table, image, list, code block, header, footer).
- [x] Headers and footers are identified and excluded from embeddings.

### Indexing
- [x] Each chunk carries metadata: document, page, section, element_type,
      chunk_id, source, char_count, created_at.
- [x] Chunking respects element type: headings/tables/code/lists are never
      split; paragraphs use `RecursiveCharacterTextSplitter` with size 800
      and overlap 150.
- [x] Embeddings generated locally via `BAAI/bge-base-en-v1.5`.
- [x] FAISS index is persisted to disk and reloadable on restart.
- [x] Index supports full rebuild via API and CLI.

### Retrieval & generation
- [x] Query is cleaned before embedding (whitespace, control chars).
- [x] FAISS returns top 10 candidates.
- [x] `BAAI/bge-reranker-base` re-ranks to top 5.
- [x] Prompt enforces: answer only from context, cite sources, refuse when
      unsupported.
- [x] LLM call goes to Groq using the latest high-quality free model.
- [x] Answer payload includes: text, citations (doc, page, section, chunk_id),
      confidence band (High/Medium/Low) + numeric percent, processing time.
- [x] When retrieval similarity is below the configured floor, the system
      returns the canonical "information not found" response -- no fabrication.

### API
- [x] `POST /ask` -- accepts a query, returns the structured answer payload.
- [x] `POST /rebuild-index` -- triggers a full re-index of `data/raw/`.
- [x] `GET /health` -- returns service status and dependency reachability.
- [x] `GET /metrics` -- returns counters and latency histograms.
- [x] All request/response bodies are Pydantic models.
- [x] Errors return structured JSON, not HTML stack traces.

### UI
- [x] Sidebar: upload, rebuild index, system stats, settings.
- [x] Main panel: question box, answer card, confidence badge, processing
      time, source cards, expandable retrieved context.
- [x] Minimalist enterprise styling, dark-mode compatible.
- [x] Responsive layout on at least desktop and tablet widths.

### Observability
- [x] Structured logging (JSON) with correlation IDs per request.
- [x] Logged events: request start/end, indexing start/end, retrieval timing,
      OCR fallback usage, LLM latency, errors, warnings.
- [x] Latency metrics exposed via `/metrics`.

### Evaluation
- [x] Benchmark question set lives in `evaluation/benchmarks/`.
- [x] Evaluator computes: retrieval precision, average response time, average
      retrieval time, citation accuracy, hallucination rate.
- [x] Eval runner is invokable via `scripts/run_eval.py`.

### Configuration
- [x] Every tunable is in `.env` and read via `config/settings.py`.
- [x] Tunables include: chunk size, chunk overlap, top-K retrieval, top-K
      rerank, embedding model, reranker model, LLM model, OCR enable flag,
      log level, confidence floor.

---

## Non-functional requirements

- [x] PEP 8 compliant, type-hinted, docstring-covered.
- [x] No hardcoded values in business logic.
- [x] System runs end-to-end on CPU.
- [x] System runs on Python 3.11.
- [x] Cold start to first answer (post-index) under 10 seconds on a modest
      laptop, excluding LLM network latency.

---

## Documentation deliverables

- [x] `README.md` -- overview, quickstart, run instructions.
- [x] `ARCHITECTURE.md` -- system design and module map.
- [x] `docs/setup.md` -- full environment setup including OCR system deps.
- [x] `docs/api.md` -- endpoint reference (auto-generated where possible).
- [x] `docs/design-decisions.md` -- why this stack, why this chunking, why this
      OCR strategy.
- [x] `docs/limitations.md` -- known limits and future-work pointers.
- [x] `docs/deployment.md` -- local, Docker, and notes for cloud deployment.
- [x] `EVALUATION.md` -- how to run and interpret the eval suite.
- [x] `docs/adr/` -- at least three ADRs covering significant decisions.
- [x] `docs/interview-prep.md` -- anticipated technical questions with answers.
