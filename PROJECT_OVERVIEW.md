# PROJECT_OVERVIEW.md — Consolidated Context Briefing

> A single-source briefing that synthesizes every planning document in this repo plus the
> frontend/UI design skills under `.agents/skills/`. It exists so a new engineer (or agent)
> can understand the whole system, its constraints, and its UI design language in one read.
>
> This document **summarizes and cross-links**; the referenced files remain the source of
> truth. If anything here disagrees with `CLAUDE.md`, `SPEC.md`, `ARCHITECTURE.md`,
> `PLAN.md`, `EVALUATION.md`, or `system_prompt.md`, those files win.

---

## 0. Project status (read first)

**This repo is at the planning / specification stage. No application code exists yet.**

- The only code currently on disk is the Python virtual environment (`venv/`).
- There is **no `app/` package, no `main.py`, no `streamlit_app.py`** yet — they are
  described in the docs but not implemented.
- What exists today: the authoritative docs, the dependency pin list, the example env
  file, the system-prompt spec, and five frontend design skills.

Everything in sections 1-11 below describes the **intended** system per the specs. Section
12 is the UI design guidance to apply when the frontend is actually built (Phase 8).

---

## 1. What the system is

An **Enterprise Knowledge Assistant**: a production-oriented Retrieval-Augmented Generation
(RAG) system over uploaded PDFs. Users upload documents, ask natural-language questions,
and get **grounded, cited answers** with **confidence scores** and **source previews**.

Core promises:

- **Grounded generation.** Answers come only from retrieved context; the system refuses
  (with a fixed canonical message) when retrieval confidence is below a floor — no
  fabrication.
- **Element-aware ingestion.** Headings, paragraphs, tables, lists, and code blocks are
  extracted and chunked by structure (tables/lists/code never split).
- **Smart OCR.** Digital PDFs go through PyMuPDF; only scanned PDFs fall back to Tesseract.
- **Two-stage retrieval.** Bi-encoder recall (`bge-base-en-v1.5`) then cross-encoder
  precision (`bge-reranker-base`).
- **Observable & measurable.** JSON logs with correlation IDs, per-stage latency metrics,
  and a reproducible evaluation suite.

It is explicitly **not a tutorial project** — the code, architecture, and docs are meant to
read like an internal enterprise platform.

---

## 2. Tech stack (locked)

| Layer            | Choice                                   | Pinned in `requirements.txt`        |
|------------------|------------------------------------------|-------------------------------------|
| Language         | Python 3.11                              | —                                   |
| Orchestration    | LangChain                                | `langchain==0.3.7` (+ community, text-splitters, groq) |
| LLM              | Groq (latest high-quality free model)    | `groq==0.11.0`, `langchain-groq==0.2.1` |
| Embeddings       | `BAAI/bge-base-en-v1.5` (local)          | `sentence-transformers==3.2.1`, `transformers==4.46.2` |
| Re-ranker        | `BAAI/bge-reranker-base` (local)         | (same as above)                     |
| Deep learning    | PyTorch                                  | `torch>=2.4.0`                      |
| Vector store     | FAISS (persisted to disk)                | `faiss-cpu==1.9.0`                  |
| PDF parsing      | PyMuPDF (first), Tesseract OCR (fallback)| `pymupdf==1.24.13`, `pytesseract==0.3.13`, `Pillow==11.0.0` |
| API              | FastAPI + Uvicorn                        | `fastapi==0.115.5`, `uvicorn[standard]==0.32.0`, `python-multipart==0.0.17` |
| UI               | Streamlit (HTTP client of the API)       | `streamlit==1.40.1`, `requests==2.32.3` |
| Config           | python-dotenv + pydantic-settings        | `pydantic-settings==2.6.1`, `python-dotenv==1.0.1` |
| Validation       | Pydantic v2                              | `pydantic==2.9.2`                  |
| Logging          | stdlib `logging` + JSON formatter        | `python-json-logger==2.0.7`        |
| Testing          | pytest (+ asyncio, httpx)                | `pytest==8.3.3`, `pytest-asyncio==0.24.0`, `httpx==0.27.2` |

New top-level dependencies must be flagged explicitly and added to `requirements.txt` and
`ARCHITECTURE.md`.

**GPU note:** Default `DEVICE=cpu`; the system must run end-to-end on CPU. On the
developer's RTX 5090 Laptop (Blackwell, sm_120) install the **CUDA 12.8** PyTorch build
manually before the rest (`pip install torch --index-url https://download.pytorch.org/whl/cu128`).

---

## 3. Architecture

### Layered component view

```
Streamlit UI (app/ui)
      │  HTTP
      ▼
FastAPI (app/api)        /ask  /rebuild-index  /health  /metrics
      ▼
Services (app/services)  QueryService · IndexingService · HealthService
      │                                   │
      ▼                                   ▼
Ingestion (app/ingestion)          RAG (app/rag)
  PDF detect → PyMuPDF / OCR         retrieval/  Embedder · VectorStore(FAISS) · Retriever · Reranker
  → Element classify → Chunk         generation/ PromptBuilder · LLMClient(Groq) · AnswerAssembler
      └──────────────┬───────────────────┘
                     ▼
              data/ (raw · processed · vector_store)
```

### Module responsibilities (from `ARCHITECTURE.md` §2)

- **`app/config/`** — loads `Settings` via pydantic-settings; owns logging config; no
  business logic. Config is **injected, never imported globally**; only this package reads
  `os.environ`.
- **`app/models/`** — framework-agnostic Pydantic domain types, the project's lingua
  franca: `DocumentElement`, `Chunk`, `Citation`, `Answer`, `RetrievalResult`,
  `RerankedResult` (plus `ElementType`, `BoundingBox`, `ConfidenceBand`). Must not import
  FastAPI / FAISS / LangChain.
- **`app/utils/`** — pure helpers: text cleaning, hashing, timing context manager, ID
  generation. No I/O, no global state.
- **`app/ingestion/document_processing/`** — `pdf_detector`, `pymupdf_extractor`,
  `ocr_extractor`, `element_classifier`, `chunker`, `metadata_extractor`. Entry point:
  `IngestionPipeline.run(pdf_path) -> list[Chunk]`.
- **`app/rag/retrieval/`** — `embedder`, `vector_store`, `retriever`, `reranker`. Entry
  point: `RetrievalPipeline.run(query) -> list[RerankedResult]`. **Never calls the LLM.**
- **`app/rag/generation/`** — `prompt_builder`, `llm_client`, `answer_assembler`. Entry
  point: `GenerationPipeline.run(query, results) -> Answer`.
- **`app/rag/prompts/`** — versioned prompt templates (no code).
- **`app/services/`** — orchestration + factories: `QueryService.ask`,
  `IndexingService.rebuild`, `HealthService.check`. Wires concrete implementations from
  `Settings`.
- **`app/api/`** — thin FastAPI routers; `schemas/` holds API request/response models
  (distinct from domain models so contracts can evolve independently).
- **`app/ui/`** — Streamlit pages; a **client of the API over HTTP**, never imports
  `app/services/` directly.
- **`app/middleware/`** — correlation IDs, request logging, exception handler mapping
  known errors to structured JSON.
- **`app/evaluation/`** — `runner`, `metrics`, `benchmarks/` JSON.

### Dependency rule

Strict bottom-to-top, no cycles:
`utils → models → config → (ingestion, rag, evaluation) → services → api / ui`.
`models`, `config`, `utils` are leaf packages. A module never imports from a layer above
it. Interfaces (ABCs) sit in front of VectorStore, Embedder, LLMClient, and Reranker so
implementations can be swapped via the factory in `services/`.

### Fail-loud / fail-graceful

Missing API keys or models → **crash on boot** with a clear message. Per-request failures
→ **structured JSON error**, never a raw 500 stack trace to the user.

---

## 4. Data flow

**Ingestion** (writes to `data/`; only `scripts/` triggers rebuilds, never `app/`):

```
PDF upload → save to data/raw/<doc_id>.pdf → IngestionPipeline.run()
  → PdfDetector.is_digital()  → True: PyMuPDFExtractor  | False: OcrExtractor
  → ElementClassifier.classify → Chunker.chunk → Embedder.embed → VectorStore.add
→ VectorStore.persist()
```

**Query**:

```
POST /ask {query} → QueryService.ask(query)
  → clean(query)
  → RetrievalPipeline: Embedder.embed → VectorStore.search(top_k=10) → Reranker.rerank → top 5
  → GenerationPipeline: PromptBuilder.build → LLMClient.complete → AnswerAssembler.assemble
       → compute confidence from (avg rerank score, top similarity) → attach citations
→ return Answer  (text, citations, confidence band + percent, processing time)
```

If the top rerank score is below `CONFIDENCE_FLOOR`, `AnswerAssembler` returns the canonical
refusal **without calling the LLM at all**.

---

## 5. Key design decisions (the "why")

- **FAISS over Qdrant/Chroma** — local-first, zero external service; wrapped behind a
  `VectorStore` interface so swapping to Qdrant is a one-file change.
- **Cross-encoder reranking** — bi-encoder recall is fast but coarse; a cross-encoder over
  the top 10 catches semantic matches the embedding misses, at the cost of one CPU pass
  over ≤10 short texts.
- **PyMuPDF-first OCR** — OCR is expensive and lossy; detect selectable text first and only
  fall back to Tesseract when none exists, avoiding OCR artifacts in embeddings.
- **Element-aware chunking** — splitting a table mid-row or a heading from its section
  destroys retrievable structure; chunk by the unit of meaning users search for.
- **Confidence band + percent** — engineers want a number, UI users want a glanceable
  label; both derive from the same raw signal so they cannot disagree.
- **Separate pure `models/` package** — domain types must not depend on FastAPI/FAISS/
  LangChain, keeping the pipeline testable without the framework.

**Extensibility seams** (already abstracted): new file types (DOCX/PPTX/HTML extractors),
new vector store, new embedder (via `.env`), hybrid BM25+vector search, auth/RBAC
middleware, and split API/indexing deploy (they communicate via the persisted index).

---

## 6. Build plan (phases — strictly ordered)

Do not start phase N+1 until phase N's acceptance criteria are all met. Each phase ends
with: run tests, update `ARCHITECTURE.md` if structure changed, tick the boxes.

| Phase | Name | Goal |
|------:|------|------|
| 0 | Repository foundation | Directory tree, clean `requirements.txt` install, `.env.example` covers every tunable, `config/settings.py` + `config/logging.py`, pytest harness runs. |
| 1 | Domain models | `elements`, `chunks`, `retrieval`, `answer` Pydantic v2 models (frozen where possible); import without FastAPI/FAISS/LangChain. |
| 2 | Utilities & logging | `utils/text`, `utils/hashing`, `utils/timing`; `middleware/correlation`, `middleware/errors`. |
| 3 | Ingestion pipeline | `pdf_detector`, `pymupdf_extractor`, `ocr_extractor`, `element_classifier`, `chunker`, `metadata_extractor`, `IngestionPipeline`. |
| 4 | Retrieval pipeline | `Embedder`/`BgeBaseEmbedder`, `VectorStore`/`FaissVectorStore`, `Retriever`, `Reranker`/`BgeRerankerBase`, `RetrievalPipeline`. |
| 5 | Generation pipeline | `system_prompt.md`, `prompt_builder`, `llm_client`/`GroqClient`, `answer_assembler`, confidence-floor short-circuit. |
| 6 | Services & orchestration | `QueryService`, `IndexingService` (idempotent), `HealthService`, settings-driven factory. |
| 7 | FastAPI surface | `api/schemas/`, routers for `/ask`, `/rebuild-index`, `/health`, `/metrics`; correlation + error middleware; p50/p95 per stage. |
| 8 | Streamlit UI | `streamlit_app.py`, `ui/pages/ask`, `ui/pages/admin`, reusable `ui/components/` (answer card, source card, confidence badge), custom CSS, `api_client.py`. |
| 9 | Evaluation | Benchmark set (≥15 Qs, ≥3 docs), `metrics.py`, `runner.py`, `scripts/run_eval.py`. |
| 10 | Documentation pass | `README`, `docs/setup`, `docs/api`, `docs/design-decisions`, `docs/limitations`, `docs/deployment`, 3 ADRs, `docs/interview-prep`. |
| 11 | Polish | Remove TODOs, verify every `SPEC.md` box, pin a final eval report, tag `v1.0.0`. |

A module is **done** only when: conventions pass, the public interface matches what was
agreed, pytest covers happy path + ≥1 failure mode, `ARCHITECTURE.md` references it, new
tunables are in `.env.example` + `settings.py`, and `PLAN.md` is updated.

---

## 7. API surface

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ask` | POST | Accepts a query, returns the structured `Answer` payload (text, citations, confidence band + percent, processing time). |
| `/rebuild-index` | POST | Triggers a full re-index of `data/raw/`. |
| `/health` | GET | Service status + dependency reachability (Groq reachable, models loadable, index loadable). |
| `/metrics` | GET | Request counters and p50/p95 latency histograms per stage. |

All request/response bodies are Pydantic models. Errors return structured JSON, never HTML
stack traces.

---

## 8. Evaluation

The eval suite is a **regression net** (not a publishable benchmark) to catch silent drift.

- **Benchmark set** — `app/evaluation/benchmarks/questions.json`. Each item: `id`,
  `question`, `expected_source_documents`, `expected_pages`, `answer_must_contain`,
  `answer_must_not_contain`, `category`. Minimum: ≥15 questions, ≥3 documents, covering
  categories `factual_lookup`, `multi_hop`, `unsupported`, `numeric`, `definition`.
- **Metrics:**
  - **Retrieval precision@5** — fraction of questions where ≥1 of the top-5 reranked chunks
    comes from an expected doc + page.
  - **Citation accuracy** — fraction of answers whose cited chunks actually contain the
    `answer_must_contain` substrings (penalizes citation hallucination).
  - **Hallucination rate** — non-refusal on an `unsupported` question, or any
    `answer_must_not_contain` string appearing. **Target < 5%.**
  - **Refusal rate on unsupported** — should be **100%**.
  - **Latency** — p50/p95 per stage (retrieval, rerank, generation, end-to-end `/ask`).
  - **Index health** — docs indexed, chunk count, mean chunk size, index file size.
- **Run:** `python scripts/run_eval.py` → walks the set serially → writes a markdown report
  to `docs/eval-reports/YYYY-MM-DD-HHMM.md` → prints a one-line summary.
- **Interpreting:** low precision + high citation accuracy ⇒ chunking splits evidence;
  high precision + low citation accuracy ⇒ tighten the citation instruction;
  hallucination on `unsupported` ⇒ confidence floor too low or LLM overriding the prompt.

---

## 9. Configuration (every tunable lives in `.env`)

No hardcoded model names, paths, chunk sizes, or top-K values in code — only
`config/settings.py` reads them. Defaults from `.env.example`:

| Variable | Default | Meaning |
|----------|---------|---------|
| `GROQ_API_KEY` | (required) | Crashes on boot if missing. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Set to the current best free Groq model at deploy time. |
| `GROQ_TIMEOUT_SECONDS` / `GROQ_MAX_RETRIES` | `30` / `2` | LLM call resilience. |
| `EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | Local embedder. |
| `RERANKER_MODEL` | `BAAI/bge-reranker-base` | Local cross-encoder. |
| `DEVICE` | `cpu` | `cpu` or `cuda` for local models. |
| `EMBEDDING_BATCH_SIZE` | `32` | Lower if CPU OOM. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `150` | Paragraph chunking (chars). |
| `TOP_K_RETRIEVAL` / `TOP_K_RERANK` | `10` / `5` | Vector candidates / rerank survivors. |
| `CONFIDENCE_FLOOR` | `0.25` | Below this rerank score, refuse instead of calling the LLM. |
| `OCR_ENABLED` / `TESSERACT_CMD` | `true` / (PATH) | OCR fallback toggle + binary override. |
| `DATA_DIR` / `RAW_DIR` / `PROCESSED_DIR` / `VECTOR_STORE_DIR` | `data` / `data/raw` / `data/processed` / `data/vector_store` | Storage paths. |
| `API_HOST` / `API_PORT` / `CORS_ORIGINS` | `0.0.0.0` / `8000` / `http://localhost:8501` | API binding + CORS. |
| `API_BASE_URL` | `http://localhost:8000` | Where the UI reaches the API. |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | Logging. |

Never commit `.env`, `data/` contents, or `*.faiss` files. Never log API keys, machine file
paths, or PII — log message IDs and document hashes.

---

## 10. Grounding contract (system prompt)

`system_prompt.md` is the canonical prompt used by `PromptBuilder`. Treated as
configuration: change deliberately, version in git, re-run the eval after edits.

**Answer rules (priority order):** (1) answer **only** from context, else return the exact
refusal string; (2) every claim is attributable, cited inline as `[doc: <name>, page: <page>]`;
(3) be concise (2-5 sentences typical); (4) be precise with numbers/names/dates, never
invent; (5) surface conflicts rather than choosing; (6) no names, no editorializing, no
"based on the provided context" filler.

**Context format per reranked chunk** (highest rerank score first, soft token cap):

```
[chunk_id: <id>] [doc: <document_name>] [page: <page>] [section: <section>]
<chunk text>
```

**Canonical refusal — must match byte-for-byte** (the eval suite checks it literally; it
appears both in prompt rule 1 and is returned by `AnswerAssembler` before the LLM is ever
called when confidence is below floor):

```
I could not find this information in the provided documents.
```

---

## 11. Coding conventions (non-negotiable — treat violations as bugs)

From `CLAUDE.md` §4-5, §8. Applies to **Python source**:

1. **File-path comment on line 1**, e.g. `# app/rag/retrieval/retriever.py` (no blank line
   before it).
2. **Single quotes** for all strings (double quotes only when the string contains a single
   quote; docstrings use `"""..."""`).
3. **No argparse** — CLI entry points use interactive `input()` in a `while True:` menu loop
   that exits on an explicit `quit` option.
4. **ASCII only in source files** — no smart quotes, em dashes, ellipsis chars, arrows, or
   emoji in `.py`. (Markdown docs like this one **may** use Unicode.)
5. **Complete files only** — emit full file contents, never diffs or `# ... unchanged`.
6. **Type hints on every signature** incl. return types; `from __future__ import annotations`
   at the top of every module.
7. **Google-style docstrings** on every public function, class, and module.
8. **No `print()` in library code** — use the configured logger (`print()` only in Streamlit
   pages and CLI menu loops).
9. **No bare `except`** — always catch a specific exception class.
10. **Imports grouped & sorted:** stdlib, third-party, local, one blank line between groups.

Architectural principles: separation of concerns (no module imports a layer above it),
config injected not globally imported, pure pipeline stages, interfaces over
implementations, fail loudly at startup / gracefully at runtime.

**Working agreement:** plan before coding (state interfaces + tests + acceptance first),
one module at a time, tests live with the code (no network/GPU), documentation is part of
done (write an ADR for significant decisions), no silent scope expansion.

---

## 12. Frontend / UI design guidance (Streamlit-adapted)

> **Why this is adapted.** The five skills under `.agents/skills/` are written for
> **React / Tailwind / Next.js / Motion / GSAP**. This project's UI is **Streamlit + custom
> CSS** (`SPEC.md`: "minimalist enterprise styling, dark-mode compatible, responsive";
> `PLAN.md` Phase 8). So the React/Tailwind/Motion **specifics do not apply** — what carries
> over is the **taste and discipline**. The most directly relevant skill is **`minimalist-ui`**,
> whose editorial-minimalist aesthetic matches the SPEC almost exactly.

### 12.1 The aesthetic target

Premium **utilitarian minimalism**: a calm, document-style, editorial interface — closer to
a refined internal tool than a marketing landing page. Quiet sophistication over spectacle.
*(`minimalist-ui`)*

### 12.2 Anti-slop discipline (what to avoid)

Avoid the LLM design defaults that read as generic AI output:
*(`design-taste-frontend`, `redesign-existing-projects`, `high-end-visual-design`)*

- AI purple/blue gradient glow; neon; heavy glassmorphism on everything.
- `Inter`/`Roboto`/`Open Sans` as the default typeface.
- Three equal feature cards; everything centered and symmetrical.
- Generic `box-shadow` (`shadow-md`/`shadow-lg`); pure-black drop shadows.
- Title Case on every header; exclamation marks; "Oops!" errors.
- AI copywriting clichés: "Elevate", "Seamless", "Unleash", "Next-Gen", "Game-changer",
  "Delve". Write plain, specific language.

### 12.3 Typography

*(`minimalist-ui`, `high-end-visual-design`, `redesign-existing-projects`)*

- Pick a sans with character over default Inter (system stacks like `SF Pro Display` /
  `Geist` / `Helvetica Neue` are fine for an enterprise tool). Optional editorial serif for
  the app title only.
- Headings: tight tracking (`-0.02em` to `-0.04em`), tight line-height (~1.1), heavy and
  intentional. Use sentence case, not Title Case.
- Body: line-height ~1.6, width capped (~65ch) for readability.
- Body text is **off-black** (`#111111` / `#2F3437`), never pure `#000`. Secondary text
  muted gray (`#787774`).
- **Tabular figures** (`font-variant-numeric: tabular-nums`) for the confidence percent,
  latency numbers, and any metric — they must align.
- Build hierarchy with **weight** (Medium 500 / SemiBold 600), not size alone.
- Render keyboard shortcuts / metadata in **monospace** (`Geist Mono` / `SF Mono` /
  `JetBrains Mono`) via `<kbd>`-style chips.

### 12.4 Color

*(`minimalist-ui`, `redesign-existing-projects`)*

- Warm monochrome canvas: white `#FFFFFF` or warm bone `#F7F6F3` / `#FBFBFA`; card surface
  `#F9F9F8`; structural borders `#EAEAEA` / `rgba(0,0,0,0.06)`.
- **One accent color, locked across the whole app**, saturation < 80%. One consistent gray
  family (do not mix warm and cool grays).
- Color is a scarce resource — use muted, washed-out pastels for tags/badges only. Map the
  **confidence band** to the `minimalist-ui` pastel set:
  - **High** → pale green `#EDF3EC` bg, text `#346538`
  - **Medium** → pale yellow `#FBF3DB` bg, text `#956400`
  - **Low** → pale red `#FDEBEC` bg, text `#9F2F2D`

### 12.5 Spacing, shape & materiality

*(`minimalist-ui`, `high-end-visual-design`)*

- Generous macro-whitespace; let sections breathe. Constrain content width
  (`max-w-4xl`/`max-w-5xl` equivalent) so it doesn't stretch edge-to-edge.
- **One corner-radius scale** (crisp `8px`-`12px` for cards; avoid `rounded-full` pills on
  large containers).
- **Near-zero shadows.** No heavy drop shadows. If elevation is needed, ultra-diffuse and
  low opacity (`< 0.05`), tinted to the background hue — never pure black. Prefer grouping
  by `border` / divider / whitespace over cards; use a card only when elevation
  communicates real hierarchy.

### 12.6 Component mapping (SPEC widgets → minimalist vocabulary)

The SPEC/Phase-8 widgets, expressed in this design language:

- **Answer card** — flat surface, `1px solid #EAEAEA` border, generous padding (24-40px),
  no shadow. Inline citations styled as subtle monospace/linked chips.
- **Confidence badge** — small pill, uppercase, wide tracking, tiny type; background from
  the pastel map in 12.4; numeric percent in tabular figures next to the band label.
- **Source cards** — compact cards showing doc · page · section · chunk_id (metadata in
  monospace), with the chunk snippet; consistent baseline alignment across cards.
- **Expandable retrieved context** — accordion as **hairline dividers only**
  (`border-bottom: 1px solid #EAEAEA`), sharp `+` / `-` toggle, no nested boxes.
- **Sidebar** — upload, rebuild index, system stats, settings; keep it quiet and grouped.

### 12.7 Interactive states (build the full cycle, not just success)

*(`design-taste-frontend`, `redesign-existing-projects`)*

- **Loading:** skeleton placeholders matching the answer/source-card shape — not a generic
  spinner — while `/ask` and `/rebuild-index` run.
- **Empty:** a composed "getting started" view before any PDF is indexed (how to upload +
  rebuild), not a blank panel.
- **Error:** clear, inline, direct messages ("Connection failed. Please try again."), never
  a browser alert or a raw stack trace.
- **Feedback:** subtle `:active` press (`scale(0.98)` / `translateY(1px)`); smooth 200-300ms
  transitions on interactive elements.

### 12.8 Accessibility (requirements, not optional)

*(`design-taste-frontend`, `redesign-existing-projects`)*

- WCAG **AA** contrast on every badge, button, input, placeholder, helper/error text
  (4.5:1 body, 3:1 large text). Verify the confidence-badge text-on-pastel pairs above.
- Label **above** input; never placeholder-as-label.
- Visible keyboard focus rings; meaningful `alt` text on images.

### 12.9 Theme consistency & dark mode

*(`design-taste-frontend`, `redesign-existing-projects`)*

- The whole app is **one theme** — no light section sandwiched in a dark page (or vice
  versa). Honor `prefers-color-scheme` for the SPEC's dark-mode requirement; set the base
  theme once. In dark mode use off-black (`#0a0a0a` / `#121212`), not pure black, and keep
  the same single accent.

### 12.10 Content & copy discipline

*(`minimalist-ui`, `redesign-existing-projects`)*

- Concise; data breathes; no data-dump tables. Real typographic quotes (" "), no straight
  ASCII quotes, no em-dash flourishes. Active voice. No Lorem Ipsum, no fake round numbers,
  no AI clichés (see 12.2).

### 12.11 Streamlit application notes

- Inject custom CSS via a dedicated styles module / `st.markdown(..., unsafe_allow_html=True)`;
  set the base palette in `.streamlit/config.toml`.
- Build the answer card, source card, and confidence badge as **reusable components**
  (`app/ui/components/`) per Phase 8; all API calls go through one `api_client.py` with
  consistent error handling.
- Responsive at desktop and tablet widths.

### 12.12 Explicitly out of scope for this UI

These skill mechanics **do not apply** to a Streamlit data tool and should not be pulled in:
React/Tailwind utility classes, Motion/GSAP scroll-hijacking (sticky-stack, horizontal-pan),
React Server Components, magnetic-button physics, and the `imagegen-frontend-web` skill's
"one generated hero image per section" rule (that is for marketing landing pages, not an
internal Q&A tool). Only the underlying **taste, restraint, and composition discipline**
carry over.

---

## 13. Repo map (what each real file is)

> Excludes `venv/` (the virtual environment) and `Architecture-Overview.png` (a rendered
> diagram of section 3).

| File | What it is |
|------|------------|
| `CLAUDE.md` | Source-of-truth instructions for agents: stack, conventions, principles, layout, do-nots. |
| `SPEC.md` | Assignment requirements distilled into a verifiable acceptance checklist. |
| `ARCHITECTURE.md` | System design: component view, module responsibilities, data flow, dependency graph, decisions. |
| `PLAN.md` | Phased build plan (Phases 0-11) with per-phase acceptance criteria. |
| `EVALUATION.md` | Benchmark methodology, metrics, how to run, how to interpret. |
| `README.md` | Public overview, quickstart, configuration table, repo map. |
| `system_prompt.md` | Canonical LLM system prompt spec + byte-exact refusal string. |
| `requirements.txt` | Pinned dependency list (Python 3.11). |
| `.env.example` | Every tunable with defaults and explanations (copy to `.env`). |
| `.gitignore` | Ignores `venv/`, `data/` contents, `*.faiss`, `.env`, logs, eval reports. |
| `skills-lock.json` | Pins the five `.agents/skills/` to their GitHub source + content hashes. |
| `.agents/skills/minimalist-ui/SKILL.md` | Editorial minimalist UI protocol — **most relevant** to this project's UI. |
| `.agents/skills/design-taste-frontend/SKILL.md` | Anti-slop frontend skill: brief inference, dials, design-system map, directives. |
| `.agents/skills/high-end-visual-design/SKILL.md` | "$150k agency" aesthetic: banned defaults, variance engine, haptic micro-aesthetics. |
| `.agents/skills/redesign-existing-projects/SKILL.md` | Audit-first upgrade checklist for existing UIs (framework-agnostic). |
| `.agents/skills/imagegen-frontend-web/SKILL.md` | Image art-direction skill (one image per section) — largely out of scope here. |
| `PROJECT_OVERVIEW.md` | This document. |

---

## 14. Sources

This briefing was synthesized from, and stays subordinate to, the following files in this
repo: `CLAUDE.md`, `SPEC.md`, `ARCHITECTURE.md`, `PLAN.md`, `EVALUATION.md`, `README.md`,
`system_prompt.md`, `requirements.txt`, `.env.example`, `.gitignore`, `skills-lock.json`,
and the five skills under `.agents/skills/` (`minimalist-ui`, `design-taste-frontend`,
`high-end-visual-design`, `redesign-existing-projects`, `imagegen-frontend-web`).
