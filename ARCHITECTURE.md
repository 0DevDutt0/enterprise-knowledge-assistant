# ARCHITECTURE.md — System Design

This document describes the architecture of the Enterprise Knowledge
Assistant. It is the canonical reference for module boundaries and data
flow. Update it whenever a structural change is introduced.

---

## 1. High-level view

```
                     +---------------------------+
                     |    Streamlit UI (app/ui)  |
                     +-------------+-------------+
                                   |
                                   v
                     +---------------------------+
                     |   FastAPI (app/api)       |
                     |  /ask /rebuild-index      |
                     |  /health /metrics         |
                     +-------------+-------------+
                                   |
                                   v
                     +---------------------------+
                     |   Services (app/services) |
                     |   - QueryService          |
                     |   - IndexingService       |
                     |   - HealthService         |
                     +------+-------------+------+
                            |             |
                            v             v
        +---------------------------+   +---------------------------+
        | Ingestion (app/ingestion) |   |   RAG (app/rag)           |
        |  - PDF detection          |   |   retrieval/              |
        |  - PyMuPDF extractor      |   |   - Embedder              |
        |  - OCR fallback           |   |   - VectorStore (FAISS)   |
        |  - Element classifier    |   |   - Retriever              |
        |  - Chunker                |   |   - Reranker              |
        +--------------+------------+   |   generation/             |
                       |                |   - PromptBuilder         |
                       |                |   - LLMClient (Groq)      |
                       v                |   - AnswerAssembler       |
                +-------------+         +---------------------------+
                |  data/      |
                |  - raw      |
                |  - processed|
                |  - vector_  |
                |    store    |
                +-------------+
```

---

## 2. Module responsibilities

### `app/config/`
- Loads environment via Pydantic Settings.
- Exposes a single `Settings` instance constructed at startup.
- Owns logging configuration.
- No business logic.

### `app/models/`
- Pydantic domain models, framework-agnostic.
- Key types: `DocumentElement`, `Chunk`, `Citation`, `Answer`,
  `RetrievalResult`, `RerankedResult`, `ConversationTurn`.
- These models flow through every layer; they are the project's lingua franca.

### `app/utils/`
- Pure helpers: text cleaning, hashing, timing context manager, ID
  generation. No I/O, no global state.

### `app/ingestion/document_processing/`
- `pdf_detector.py` — decides digital vs scanned.
- `pymupdf_extractor.py` — extracts elements from digital PDFs.
- `ocr_extractor.py` — Tesseract fallback path.
- `element_classifier.py` — assigns `ElementType` to raw extractions.
- `chunker.py` — element-aware chunking per the rules in `SPEC.md`.
- `metadata_extractor.py` — populates `Chunk.metadata`.

Public entry point: `IngestionPipeline.run(pdf_path) -> list[Chunk]`.

### `app/rag/retrieval/`
- `embedder.py` -- wraps `BAAI/bge-base-en-v1.5`, CPU/GPU configurable.
- `vector_store.py` -- FAISS wrapper with persist/load. Exposes `chunks`
  property so factory can seed BM25 without a full rebuild.
- `retriever.py` -- `BaseRetriever` ABC; `Retriever` implementation embeds
  query and calls vector store, returning top-K `RetrievalResult`.
- `reranker.py` -- wraps `BAAI/bge-reranker-base`, scores and reorders.
- `query_rewriter.py` -- `QueryRewriter` ABC; `PassthroughRewriter` (no-op);
  `LLMQueryRewriter` (calls the shared `LLMClient` with a prompt template to
  expand pronouns, resolve acronyms, and make vague queries concrete before
  embedding). Falls back to original query on any error. Enabled via
  `settings.query_rewriting_enabled`.
- `bm25_retriever.py` -- `BM25Retriever` backed by `rank-bm25`'s `BM25Plus`.
  Persisted to `bm25_index.pkl` alongside the FAISS index. `BM25Plus` chosen
  over `BM25Okapi` because the Okapi IDF collapses to 0 for small corpora
  (term in exactly half the docs), making all scores zero.
- `hybrid_retriever.py` -- `HybridRetriever(BaseRetriever)` fuses `Retriever`
  and `BM25Retriever` results via Reciprocal Rank Fusion:
  `score = sum(1 / (k + rank))` across lists, k=60 (configurable via
  `settings.rrf_k`). Deduplicates by `chunk_id`. Enabled via
  `settings.retrieval_mode = 'hybrid'` (default: 'semantic').

Public entry point: `RetrievalPipeline.run(query) -> list[RerankedResult]`.

### `app/rag/generation/`
- `prompt_builder.py` — constructs the final LLM prompt from query +
  reranked context. Pulls templates from `app/rag/prompts/`.
- `llm_client.py` — thin Groq client behind an interface.
- `answer_assembler.py` — turns the LLM response + retrieval metadata
  into an `Answer` payload with citations and confidence.

Public entry point: `GenerationPipeline.run(query, results) -> Answer`.

### `app/rag/prompts/`
- Plain-text or markdown prompt templates. Versioned. No code.

### `app/services/`
- Orchestrates ingestion, retrieval, and generation.
- `QueryService.ask(query, history?) -> Answer` — accepts optional
  `list[ConversationTurn]`; forwards to generation pipeline for prompt injection.
- `IndexingService.rebuild() -> IndexStats`
- `HealthService.check() -> HealthReport`
- Owns factory functions that wire concrete implementations into the
  pipeline interfaces.

### `app/api/`
- FastAPI routers. Thin: parse the request, call the service, return the
  response. No business logic.
- `schemas/` holds request/response Pydantic models (distinct from domain
  models in `app/models/` — API contracts evolve independently).

### `app/ui/`
- Streamlit pages. Calls the FastAPI service over HTTP.
- The UI is a client of the API, not a co-process. Never imports from
  `app/services/` directly.

### `app/middleware/`
- Request logging, correlation IDs, exception handler that maps known
  errors to structured JSON responses.

### `app/evaluation/`
- `runner.py` — loads benchmark set, runs the pipeline, emits a report.
- `metrics.py` — retrieval precision, citation accuracy, hallucination
  detection logic.
- `benchmarks/` — JSON files of question/expected-source pairs.

---

## 3. Data flow

### Ingestion flow
```
PDF upload
   -> save to data/raw/<doc_id>.pdf
   -> IngestionPipeline.run()
      -> PdfDetector.is_digital()
         -> True:  PyMuPDFExtractor.extract()
         -> False: OcrExtractor.extract()
      -> ElementClassifier.classify(raw_elements)
      -> Chunker.chunk(elements)
      -> Embedder.embed(chunks)
      -> VectorStore.add(chunks, embeddings)
   -> VectorStore.persist()
```

### Query flow
```
POST /ask {query}
   -> QueryService.ask(query)
      -> clean(query)
      -> RetrievalPipeline.run(query)
         -> Embedder.embed(query)
         -> VectorStore.search(top_k=10)
         -> Reranker.rerank(query, candidates) -> top 5
      -> GenerationPipeline.run(query, reranked)
         -> PromptBuilder.build(query, reranked)
         -> LLMClient.complete(prompt)
         -> AnswerAssembler.assemble(llm_output, reranked)
            -> compute confidence from similarity + rerank scores
            -> attach citations
   -> return Answer
```

---

## 4. Dependency graph

Arrows mean "imports from". No cycles permitted.

```
api  ──>  services  ──>  rag.generation
 │           │       ──>  rag.retrieval
 │           │       ──>  ingestion
 │           │
 ui  ──> (HTTP) ──> api
 │
 │           │       ──>  models, config, utils
 │           │
 │       ingestion ──>  models, config, utils
 │       rag.*    ──>  models, config, utils
 │       evaluation──>  services, models, config
 │
 middleware ──> config, utils
```

`models`, `config`, `utils` are leaf packages — they import only from each
other and the standard library / third-party libs.

---

## 5. Key design decisions

### Why FAISS over Qdrant/Chroma
Local-first, zero external service to run for the assignment scope. Wrapped
behind a `VectorStore` interface so swapping to Qdrant is a one-file change.

### Why cross-encoder reranking
Bi-encoder retrieval is fast but coarse. A cross-encoder over the top 10
catches semantic matches that the embedding alone misses, at a cost of a
single CPU-bounded pass over <= 10 short texts.

### Why PyMuPDF-first OCR strategy
OCR is expensive and lossy. Most enterprise PDFs are digital. Detecting
selectable text first and only falling back to Tesseract when none exists
saves seconds per page and avoids OCR artifacts contaminating embeddings.

### Why element-aware chunking
Splitting a table mid-row, a heading from its section, or a code block at
an arbitrary character boundary destroys retrievable structure. Chunking
by element type preserves the unit of meaning users actually search for.

### Why confidence bands plus percent
Engineers reading the API want a number; UI users want a glanceable label.
Both are computed from the same raw signal (rerank score + retrieval
similarity) so they cannot disagree.

### Why a separate `models/` package
Domain types must not depend on FastAPI, FAISS, or LangChain. Keeping them
pure makes the pipeline testable without spinning up the framework.

---

## 6. Extensibility points

These are the seams where the system is designed to grow. Each is already
abstracted behind an interface so the change is local.

- **New file types** (DOCX, PPTX, HTML): add an extractor in
  `app/ingestion/document_processing/`, register it with the
  `IngestionPipeline` factory.
- **New vector store** (Qdrant, Weaviate, pgvector): implement
  `VectorStore` ABC, swap in the factory.
- **New embedder** (OpenAI, Cohere, local Qwen): implement `Embedder`
  ABC, swap in `.env`.
- **Hybrid search** (BM25 + vector): `BM25Retriever` + `HybridRetriever`
  implemented in Phase 13; enable with `RETRIEVAL_MODE=hybrid` in `.env`.
- **Auth / RBAC**: add middleware in `app/middleware/`, scope retrieval
  filters by user via metadata.
- **Distributed deploy**: API and indexing service can be split — they
  already communicate via persisted FAISS index, not in-memory state.
