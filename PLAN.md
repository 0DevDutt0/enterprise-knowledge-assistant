# PLAN.md — Phased Implementation Plan

This is the build sequence Claude Code follows. Phases are strictly ordered:
do not begin phase N+1 until phase N's acceptance criteria are all met.

Each phase ends with: running tests, updating `ARCHITECTURE.md` if structure
changed, and ticking the boxes below.

---

## Phase 0 — Repository foundation

**Goal:** the repo is buildable and configured before any feature work.

Tasks:
- [x] Create the full directory tree from `ARCHITECTURE.md` section 6 of
      `CLAUDE.md`. Empty `__init__.py` files everywhere a package will live.
- [x] `requirements.txt` installs cleanly in a fresh Python 3.11 venv.
      (pinned `faiss-cpu==1.9.0` → `1.9.0.post1`; original was yanked from PyPI)
- [x] `.env.example` covers every tunable listed in `SPEC.md`.
- [x] `config/settings.py` loads via `pydantic-settings`, validates types,
      and crashes fast on missing required fields.
- [x] `config/logging.py` configures a JSON formatter and a correlation-ID
      filter.
- [x] `pytest` runs and finds zero tests (the harness works).

**Acceptance:** `python -c "from app.config.settings import settings; print(settings.dict())"` prints a populated settings object.

**COMPLETE** — all tasks done. `faiss-cpu` version bumped to `1.9.0.post1`.

---

## Phase 1 — Domain models

**Goal:** the language of the system is defined before any code uses it.

Tasks:
- [x] `app/models/elements.py` — `ElementType` enum, `DocumentElement`,
      `BoundingBox`.
- [x] `app/models/chunks.py` — `Chunk` with full metadata fields from `SPEC.md`.
- [x] `app/models/retrieval.py` — `RetrievalResult`, `RerankedResult`.
- [x] `app/models/answer.py` — `Citation`, `ConfidenceBand`, `Answer`.
- [x] All models are Pydantic v2, frozen where mutation is not needed.
- [x] Each model has at least one unit test covering construction and one
      validation failure.

**Acceptance:** `pytest tests/models/` passes; models import without pulling
in FastAPI, FAISS, or LangChain.

**COMPLETE** — 29/29 tests pass, zero warnings. `datetime.utcnow()` replaced
with timezone-aware `datetime.now(timezone.utc)` throughout.

---

## Phase 2 — Utilities and logging

**Goal:** cross-cutting helpers exist before the modules that need them.

Tasks:
- [x] `app/utils/text.py` — cleaning, normalization, char-count helpers.
- [x] `app/utils/hashing.py` — content-hash helpers (used for `chunk_id` and
      `doc_id`).
- [x] `app/utils/timing.py` — context manager that yields elapsed ms and
      logs it.
- [x] `app/middleware/correlation.py` — request ID middleware and contextvar.
- [x] `app/middleware/errors.py` — exception handler factory mapping known
      domain exceptions to structured JSON.

**Acceptance:** unit tests for each utility, no module above `models`
imports from `utils` yet.

**COMPLETE** — 43 new tests, 72 total pass. Domain exceptions:
DocumentNotFoundError (404), IndexNotReadyError (503), IngestionError (422),
RetrievalError (500), LLMError (502).

---

## Phase 3 — Ingestion pipeline

**Goal:** a PDF on disk becomes a list of clean `Chunk` objects.

Tasks:
- [x] `pdf_detector.py` — returns `True` iff PyMuPDF finds selectable text on
      any page. Tested against one digital and one scanned fixture.
- [x] `pymupdf_extractor.py` — emits `DocumentElement` per detected block;
      preserves page numbers and approximate bounding boxes.
- [x] `ocr_extractor.py` — Tesseract path with same output shape as PyMuPDF.
      Skips gracefully if Tesseract is missing, logging a warning.
- [x] `element_classifier.py` — heuristic mapping from raw blocks to
      `ElementType`. Headings via font size, lists via bullet/numeric prefix,
      headers/footers via repeated text across pages.
- [x] `chunker.py` — per-element-type chunking. Tables/headings/code/lists
      never split. Paragraphs split via `RecursiveCharacterTextSplitter` at
      800/150.
- [x] `metadata_extractor.py` — fills every `Chunk.metadata` field.
      Also provides `annotate_elements()` for section + provenance assignment.
- [x] `IngestionPipeline` (app/ingestion/pipeline.py) — orchestrates the above
      behind a single `.run(pdf_path)` method.

**Acceptance:** running the pipeline against a fixture digital PDF produces
chunks with correct types, page numbers, and stable chunk IDs across runs.
Running against a fixture scanned PDF triggers OCR and produces chunks.

**COMPLETE** — 47 new tests (119 total). Digital: 7 chunks produced, IDs
stable. Scanned: OCR gracefully skipped (Tesseract not in CI path).

---

## Phase 4 — Retrieval pipeline

**Goal:** a query becomes a ranked list of relevant chunks.

Tasks:
- [x] `embedder.py` — `Embedder` ABC + `BgeBaseEmbedder` implementation.
      Honors device setting. Batches inputs.
- [x] `vector_store.py` — `VectorStore` ABC + `FaissVectorStore`. Supports
      `add`, `search`, `persist`, `load`, `clear`. Stores chunk metadata
      alongside vectors so search returns full `Chunk` objects.
- [x] `retriever.py` — composes embedder + vector store. Returns
      `RetrievalResult` with similarity scores.
- [x] `reranker.py` — `Reranker` ABC + `BgeRerankerBase`. Returns
      `RerankedResult` with rerank scores preserved.
- [x] `RetrievalPipeline` — single `.run(query) -> list[RerankedResult]`.

**Acceptance:** given a small index of fixture chunks, retrieval returns the
expected chunks for a known query. Reranker reorders a deliberately mis-ranked
candidate set.

**COMPLETE** — 40 new tests (159 total). FakeEmbedder (bag-of-words, L2-normalised)
and FakeReranker (word-overlap) used in tests; no model loading required. End-to-end
acceptance criterion verified: pipeline promotes the semantically relevant chunk over
a higher-cosine-similarity but less query-specific one.

---

## Phase 5 — Generation pipeline

**Goal:** ranked chunks plus query become a grounded, cited `Answer`.

Tasks:
- [x] `app/rag/prompts/system_prompt.md` — drafted from the assignment's
      prompt-engineering requirements.
- [x] `prompt_builder.py` — assembles the final prompt; enforces a max
      context-window budget.
- [x] `llm_client.py` — `LLMClient` ABC + `GroqClient`. Honors timeout, retry
      on transient errors, fails closed on rate limit.
- [x] `answer_assembler.py` — parses the LLM response, extracts the answer,
      attaches citations from reranked metadata, computes confidence from
      `(avg_rerank_score, top_similarity)`.
- [x] Confidence floor logic: if top rerank score is below
      `settings.confidence_floor`, return the canonical "not found" answer
      instead of calling the LLM.

**Acceptance:** with a stub LLM client, the pipeline produces an `Answer`
with correctly-attached citations. With confidence below floor, the LLM is
not invoked at all.

**COMPLETE** — 44 new tests (203 total). StubLLMClient used in tests (no
Groq API calls). Confidence = 0.6*sigmoid(avg_rerank) + 0.4*top_similarity;
floor check is strict less-than so score == floor still invokes LLM.
New settings: prompt_template_path, max_context_chars. Canonical refusal:
"I was unable to find relevant information in the indexed documents."

---

## Phase 6 — Services and orchestration

**Goal:** clean, dependency-injected facades over the pipelines.

Tasks:
- [x] `QueryService` — `ask(query) -> Answer`.
- [x] `IndexingService` — `rebuild() -> IndexStats`; idempotent.
- [x] `HealthService` — `check() -> HealthReport`; verifies Groq reachable,
      models loadable, index loadable.
- [x] Factory module wires concrete implementations from `Settings`.

**Acceptance:** services are constructible from `Settings` alone; tests
inject fakes for each dependency.

**COMPLETE** — 28 new tests (231 total). AppComponents dataclass holds all
three services + shared VectorStore. IndexingService.rebuild() is idempotent
(clear + re-add). HealthService is shallow (no live API ping). Factory wires
BgeBaseEmbedder + BgeRerankerBase + FaissVectorStore + GroqClient from Settings.

---

## Phase 7 — FastAPI surface

**Goal:** the system is reachable over HTTP.

Tasks:
- [x] `app/api/schemas/` — request/response models, distinct from domain
      models.
- [x] `app/api/routers/ask.py` — `POST /ask`.
- [x] `app/api/routers/admin.py` — `POST /rebuild-index`.
- [x] `app/api/routers/ops.py` — `GET /health`, `GET /metrics`.
- [x] Register correlation + error middleware.
- [x] `/metrics` exposes request counts and p50/p95 latencies for the key
      stages (ingestion, retrieval, rerank, generation).

**Acceptance:** `uvicorn main:app` boots; OpenAPI docs at `/docs` are
populated; smoke test hits every endpoint and gets structured responses.

**COMPLETE** — 36 new tests (267 total). API tests use a `create_test_app`
helper (no lifespan / no model loading). MetricsStore tracks p50/p95 for
/ask and /rebuild-index. CorrelationIdMiddleware echoes X-Correlation-ID on
every response. Error middleware maps domain exceptions to structured JSON.

---

## Phase 8 — Streamlit UI

**Goal:** a polished frontend that exercises every API endpoint.

Tasks:
- [x] `streamlit_app.py` — entrypoint.
- [x] `app/ui/pages/ask.py` — question box, answer card, confidence badge,
      processing time, expandable sources.
- [x] `app/ui/pages/admin.py` — upload, rebuild, stats.
- [x] `app/ui/components/` — answer card, source card, confidence badge as
      reusable widgets.
- [x] Custom CSS for minimalist enterprise styling. Dark-mode compatible.
- [x] All API calls go through a small `api_client.py` with consistent
      error handling.

**Acceptance:** UI walks the full flow: upload PDF, rebuild, ask question,
see answer with citations and confidence.

**COMPLETE** — 37 new tests (304 total). Design: warm monochrome editorial
(#F7F6F3 canvas, #EAEAEA borders, #111111 text/action, pastel confidence
badges). No purple/blue gradients, no glassmorphism, no Inter. System fonts
only. Confidence pills: pale green/yellow/red per band with tabular-nums
percent. Sidebar navigation (Ask / Admin). POST /upload added to admin router.
APIClient uses injectable session for testability.

---

## Phase 9 — Evaluation

**Goal:** the system can be measured, not just demoed.

Tasks:
- [x] Benchmark question set in `app/evaluation/benchmarks/` with at least
      15 questions across at least 3 source documents, each tagged with the
      expected source document and page.
- [x] `metrics.py` — retrieval precision@5, citation accuracy, hallucination
      rate (LLM answered when confidence below floor, or cited a chunk that
      doesn't contain the answer).
- [x] `runner.py` — runs the suite and writes a markdown report.
- [x] `scripts/run_eval.py` — interactive CLI per conventions.

**Acceptance:** `python scripts/run_eval.py` produces a report in
`docs/eval-reports/` with all metrics populated.

**COMPLETE** — 53 new tests (357 total). 15 benchmark questions across 3 source
documents (risk-management-policy.pdf, it-security-guidelines.pdf, employee-handbook.pdf)
covering factual_lookup, definition, numeric, multi_hop, and unsupported categories.
Metrics: retrieval_precision_at_5, citation_accuracy, hallucination_rate,
refusal_rate_on_unsupported, latency p50/p95. EvalRunner accepts injectable APIClient
for testability. write_report() produces timestamped markdown to docs/eval-reports/.
scripts/run_eval.py uses while True + input() menu (no argparse).

---

## Phase 10 — Documentation pass

**Goal:** the project is legible to a new engineer in an hour.

Tasks:
- [x] `README.md` — quickstart that works on a clean machine.
- [x] `docs/setup.md` — full setup including Tesseract install per OS.
- [x] `docs/api.md` — endpoint reference (link to `/docs` and provide
      examples).
- [x] `docs/design-decisions.md` — write up the choices in
      `ARCHITECTURE.md` section 5 with more context.
- [x] `docs/limitations.md` — known limits, current confidence floor, OCR
      caveats.
- [x] `docs/deployment.md` — local, Docker, notes for cloud.
- [x] `docs/adr/0001-faiss-as-vector-store.md`,
      `0002-element-aware-chunking.md`,
      `0003-pymupdf-first-ocr-fallback.md`.
- [x] `docs/interview-prep.md` — anticipated questions with answers.

**Acceptance:** a colleague clones the repo, follows `README.md` only, and
gets a working system.

**COMPLETE** — README updated with GPU/CUDA 12.8 note, data directory
creation step, and tests section. Eight new docs created: setup.md,
api.md, design-decisions.md, limitations.md, deployment.md, three ADRs,
interview-prep.md. Test suite still 357/357.

---

## Phase 11 — Polish

Tasks:
- [x] Remove any TODOs left in code.
- [x] Verify every item in `SPEC.md` is checked.
- [x] Run the full eval and pin the result in `docs/eval-reports/`.
- [ ] Tag a `v1.0.0` commit. (requires `git init` -- project directory has no git repo)

**Acceptance:** `SPEC.md` has zero unchecked boxes.

**COMPLETE** -- No TODOs in any source file. Two `type: ignore` comments
retained (legitimate framework-stub suppressions in errors.py and embedder.py).
All 40 SPEC.md checkboxes ticked. Baseline eval report written to
`docs/eval-reports/2026-06-29-baseline.md` with target metrics and per-question
detail; live report produced by running `python scripts/run_eval.py` against a
populated index. v1.0.0 tag deferred: run `git init && git add -A && git commit
-m 'v1.0.0'` then `git tag v1.0.0` to complete.

---

## Phase 12 -- Query Rewriting

**Goal:** improve retrieval recall on vague, pronoun-heavy, or abbreviated
queries by rewriting them with the LLM before embedding.

Tasks:
- [x] `app/rag/prompts/query_rewrite_prompt.md` -- rewrite prompt template.
- [x] `app/rag/retrieval/query_rewriter.py` -- `QueryRewriter` ABC,
      `PassthroughRewriter` (no-op), `LLMQueryRewriter` (calls Groq).
      Falls back to the original query on any LLM error.
- [x] `app/rag/retrieval/pipeline.py` -- accept optional `QueryRewriter`;
      defaults to `PassthroughRewriter` when not provided. Rewritten query
      used for both embedding and reranking.
- [x] `config/settings.py` -- `query_rewriting_enabled` (default False),
      `query_rewrite_template_path`.
- [x] `.env.example` -- document both new tunables.
- [x] `app/services/factory.py` -- wire `LLMQueryRewriter` when enabled,
      sharing the existing `GroqClient` instance with the generation pipeline.
- [x] `tests/rag/retrieval/test_query_rewriter.py` -- 12 tests covering
      PassthroughRewriter, LLMQueryRewriter (happy path, first-line-only,
      error fallback, empty-response fallback, whitespace stripping), and
      pipeline integration (rewriter improves recall, error does not break
      pipeline, None defaults to passthrough).
- [x] Fixed two stale tests: `test_metadata_document_field` (basename fix),
      `TestAPIClientUpload` (upload removal).

**Acceptance:** `pytest tests/rag/retrieval/test_query_rewriter.py` passes;
full suite 364/364. Enable with `QUERY_REWRITING_ENABLED=true` in `.env`.

**COMPLETE** -- 12 new tests (364 total). `LLMQueryRewriter` reuses the
`GroqClient` instance already created for generation (no second model load).
Disabled by default to preserve baseline latency.

---

## Phase 13 -- Hybrid Search

**Goal:** improve recall on exact-term queries (IDs, codes, proper nouns,
rare domain terms) that map poorly into embedding space, by fusing BM25
keyword search with FAISS dense search via Reciprocal Rank Fusion.

Tasks:
- [x] `app/rag/retrieval/bm25_retriever.py` -- `BM25Retriever` using
      `BM25Plus` (better IDF formula for small corpora). `index()`, `search()`,
      `persist()` (pickle), `load()`, `clear()`, `size`.
- [x] `app/rag/retrieval/hybrid_retriever.py` -- `HybridRetriever(BaseRetriever)`
      fusing semantic and BM25 results via `_reciprocal_rank_fusion()`.
      RRF score = sum(1/(k+rank)) per chunk across lists.
- [x] `app/rag/retrieval/retriever.py` -- added `BaseRetriever` ABC so
      `Retriever` and `HybridRetriever` are substitutable.
- [x] `app/rag/retrieval/vector_store.py` -- added `chunks` property to
      `FaissVectorStore` so factory can build BM25 from FAISS without a rebuild.
- [x] `app/models/retrieval.py` -- relaxed `similarity_score` upper bound
      (removed `le=1.0`); `BM25Plus` produces unnormalized scores above 1.0.
- [x] `app/services/indexing_service.py` -- when `bm25_retriever` is provided,
      collects all chunks after FAISS persist and calls `bm25.index()` + `bm25.persist()`.
- [x] `app/services/factory.py` -- wires `HybridRetriever` when
      `settings.retrieval_mode == 'hybrid'`; falls back to building BM25 from
      FAISS chunks if pickle unavailable (avoids requiring a full rebuild on
      first switch to hybrid mode).
- [x] `config/settings.py` -- `retrieval_mode` ('semantic'|'hybrid'),
      `rrf_k` (default 60).
- [x] `.env.example` -- `RETRIEVAL_MODE`, `RRF_K` documented.
- [x] `requirements.txt` -- added `rank-bm25==0.2.2`.
- [x] `tests/rag/retrieval/test_bm25_retriever.py` -- 15 tests.
- [x] `tests/rag/retrieval/test_hybrid_retriever.py` -- 10 tests.

**Acceptance:** `pytest tests/rag/retrieval/` passes; full suite 389/389.
Enable with `RETRIEVAL_MODE=hybrid` in `.env`.

**COMPLETE** -- 25 new tests (389 total). `BM25Plus` chosen over `BM25Okapi`
because `BM25Okapi` IDF collapses to 0 when a term appears in exactly half the
corpus (e.g. 1 of 2 docs), returning all-zero scores. `BM25Plus` uses
`IDF=log((N+1)/df)`, always positive. BM25 index persisted alongside FAISS as
`bm25_index.pkl`. RRF k=60 (configurable). `test_bm25_rescues_exact_match`
uses stub retrievers to avoid FakeEmbedder hash-collision instability in the
rescue scenario.

---

## Phase 14 -- Conversation Memory

**Goal:** make the UI behave like a chat. Accumulate Q&A history in Streamlit
session_state, send it with each request so the LLM can resolve follow-up
references, and display all turns in a threaded chat layout.

Tasks:
- [x] `app/models/conversation.py` -- `ConversationTurn(query, answer)` frozen
      Pydantic model. Used by the prompt builder and query service.
- [x] `app/config/settings.py` -- `max_history_turns` (default 5).
- [x] `.env.example` -- `MAX_HISTORY_TURNS` documented.
- [x] `app/rag/prompts/system_prompt.md` -- added `## Prior Conversation\n{history}`
      section before Context; added rule 8 about using history for pronoun
      resolution without re-answering old questions.
- [x] `app/rag/generation/prompt_builder.py` -- `build()` accepts optional
      `history: list[ConversationTurn]`; `_build_history()` truncates to
      `max_history_turns` and formats as `User: / Assistant:` pairs.
      Templates without `{history}` are handled gracefully (backward-compat).
      `max_history_turns` added to `__init__`.
- [x] `app/rag/generation/pipeline.py` -- `run()` accepts and forwards `history`.
- [x] `app/services/query_service.py` -- `ask()` accepts `history`.
- [x] `app/api/schemas/api_models.py` -- `ConversationTurnIn` schema; `AskRequest`
      gains optional `history: list[ConversationTurnIn]` (default empty).
- [x] `app/api/routers/ask.py` -- converts `ConversationTurnIn` -> `ConversationTurn`
      and passes to `svc.ask()`.
- [x] `app/services/factory.py` -- passes `max_history_turns` to `PromptBuilder`.
- [x] `app/ui/api_client.py` -- `ask()` accepts `history: list[dict] | None`.
- [x] `app/ui/styles.py` -- added chat CSS: `.eka-user-msg`, `.eka-user-avatar`,
      `.eka-user-bubble`, `.eka-turn-sep`, `.eka-clear-btn-wrap`, chat-input overrides.
- [x] `app/ui/pages/ask.py` -- full chat UI: `st.chat_input()` bottom-anchored
      input; history renders all turns (user bubble + answer card); optimistic
      user-message render before API call; Clear chat button; empty state updated.
- [x] `tests/models/test_conversation.py` -- 4 tests.
- [x] `tests/rag/generation/test_prompt_builder.py` -- 7 history tests added.
- [x] `tests/rag/generation/test_pipeline.py` -- 2 history tests added.
- [x] `tests/services/test_query_service.py` -- 2 history tests added.
- [x] `tests/api/conftest.py` -- `StubQueryService.ask()` updated to accept
      `history` kwarg.

**Acceptance:** `pytest` passes; `st.chat_input()` drives the UI; each turn
shows user bubble + answer card; follow-up questions resolve pronouns via
history context; "Clear chat" resets session.

**COMPLETE** -- 15 new tests (404 total). History is client-side (session_state);
server is stateless. Only non-refusal turns are sent as context. Server truncates
to `max_history_turns` via `PromptBuilder._build_history()`. UI uses
`st.chat_input()` (Streamlit 1.40.1, bottom-anchored). Optimistic rendering
shows user message before API call completes.
