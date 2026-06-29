# Design Decisions

Elaborates on the key choices in `ARCHITECTURE.md` section 5. Each
decision records what was chosen, what was rejected, and why. This is
the place to look when a choice seems arbitrary.

---

## FAISS over Qdrant / Chroma

**Chosen:** FAISS (persisted to disk as a flat binary index).

**Rejected:** Qdrant, Weaviate, Chroma, pgvector.

**Why:**

The assignment scope is a single-machine demo environment. Running a
Qdrant or Weaviate container adds an external dependency that increases
setup friction with no recall benefit at the scale of a few hundred
documents. FAISS runs in-process, persists to a single file, and starts
instantly.

FAISS `IndexFlatIP` (inner product on L2-normalised vectors) gives exact
cosine similarity without approximation. At <= 50k chunks the linear scan
is measured in milliseconds on CPU.

The `VectorStore` ABC means the swap to Qdrant is one file change -- the
rest of the pipeline is unaffected.

**Trade-off:** FAISS does not support filtered search (e.g. "only search
within document X"). If per-user document isolation is added later, a
metadata-capable store is needed.

---

## Cross-encoder reranking over retrieval-only

**Chosen:** BGE reranker (`bge-reranker-base`) as a second-stage ranker
over the top-10 bi-encoder results.

**Rejected:** returning bi-encoder top-K directly; BM25 fusion.

**Why:**

Bi-encoder retrieval is fast but coarse: the query and each document are
embedded independently, so the model cannot attend to query-document
interactions. A cross-encoder sees both the query and candidate chunk
simultaneously -- the attention heads can detect subtle semantic matches
and surface them above noisily high-cosine chunks.

The cost is bounded: the cross-encoder runs over at most 10 short texts
per query. On CPU with `bge-reranker-base` this is under 200ms for a
typical chunk size.

The two-stage pipeline is the same approach used in production retrieval
systems (e.g. DPR + MonoBERT, ColBERT). It is well-understood.

**Trade-off:** an additional model download (~360 MB) and an additional
inference pass per query. Justified by the measurable improvement in the
evaluation metrics.

---

## PyMuPDF-first, Tesseract fallback

**Chosen:** attempt text extraction with PyMuPDF; only call Tesseract
when PyMuPDF finds zero selectable text on a page.

**Rejected:** always-OCR; OCR-first; purely rule-based page detection.

**Why:**

OCR (Tesseract, especially) introduces transcription errors, especially
on PDFs with unusual fonts, tight kerning, or complex layouts. Digital
PDFs already contain machine-readable text layers; running OCR on them
degrades quality.

Detection is cheap: PyMuPDF's `Page.get_text()` is a few milliseconds
per page. If it returns non-empty text, the page is digital. Only pages
with empty text results fall through to Tesseract.

**Trade-off:** some PDFs contain both a text layer (for searchability)
and embedded images with different content. In those cases the text layer
wins. This is the correct behavior for standard enterprise PDFs.

---

## Element-aware chunking

**Chosen:** extract document structure (headings, paragraphs, tables,
lists, code blocks), classify each element, then apply element-type-
specific chunking rules.

**Rejected:** naive fixed-size chunking over raw text; sentence-boundary
splitting only.

**Why:**

Splitting a table at an arbitrary character position makes the chunk
unreadable. Splitting a heading from its body paragraph means retrieval
returns the heading without the content it introduces. Naive 800-char
splits cross these boundaries routinely.

Element-aware chunking preserves units of meaning:
- Tables and code blocks: stored as single chunks regardless of size.
- Headings: grouped with their following paragraph when small enough.
- Lists: stored whole to preserve item relationships.
- Long paragraphs: split by `RecursiveCharacterTextSplitter` at 800/150.

The result is that retrieved chunks are almost always independently
intelligible -- the LLM can cite them without needing surrounding context.

**Trade-off:** the classifier is heuristic (font size for headings, regex
for list prefixes). It will misclassify unusual document layouts. The
fallback for anything unclassified is `PARAGRAPH`, which is safe.

---

## Confidence as (rerank score + similarity) blend

**Chosen:** `confidence = 0.6 * sigmoid(avg_rerank) + 0.4 * top_sim`,
expressed as a 0--100 percent with three labelled bands.

**Rejected:** raw rerank score only; top-similarity only; calibrated
probability from a separate classifier.

**Why:**

The rerank score is the best single signal for answer quality -- it
directly measures query-chunk relevance. But it is unbounded and varies
with model version. The sigmoid maps it to (0, 1) stably.

Top similarity from the bi-encoder captures retrieval quality
independently of the reranker. The 60/40 blend gives more weight to
reranking (the more expensive and precise signal) while preserving some
influence from retrieval similarity.

The three bands (High >= 70%, Medium >= 40%, Low < 40%) give UI users
a glanceable quality signal without exposing the raw formula.

**Trade-off:** the thresholds (0.6/0.4 blend, 70%/40% band edges) are
heuristic and not calibrated against a labeled dataset. They should be
treated as reasonable starting points, not as probabilities.

---

## Confidence floor as a hard refusal gate

**Chosen:** if the top reranked chunk's score is strictly below
`CONFIDENCE_FLOOR`, return the canonical refusal response without
calling the LLM.

**Why:**

The most dangerous failure mode of a RAG system is confidently answering
from irrelevant context. When retrieval fails (top rerank score is near
zero), the LLM has no grounding and is likely to hallucinate. Not calling
it at all is cheaper, faster, and safer.

The floor check is strict `<` (not `<=`) so that a score exactly equal
to the floor still calls the LLM. This makes the behavior at the boundary
predictable: raising the floor by epsilon is the correct way to tighten
the policy.

**Trade-off:** the floor is a blunt instrument. A domain-specific
calibration (trained refusal classifier) would be more accurate. The
hard floor is a safe default that is easy to understand and explain.

---

## Separate `models/` package

**Chosen:** domain types (`Chunk`, `Answer`, `Citation`, etc.) live in
`app/models/` and import nothing from the application framework.

**Why:**

If `Chunk` imported from `app/rag/` or `Citation` imported from FastAPI,
unit tests for the models would need the full stack running. Keeping
models framework-agnostic means they can be instantiated and validated in
isolation -- which is exactly what the 29 model tests do.

It also creates a stable interface layer: the ingestion pipeline,
retrieval pipeline, and generation pipeline all speak the same types.

---

## Single-process API + Streamlit as HTTP client

**Chosen:** Streamlit is a standalone process that talks to the FastAPI
API over HTTP, not a co-process sharing memory.

**Rejected:** Streamlit calling service functions directly as library
imports.

**Why:**

Keeping the UI process separate means:
1. The API can be deployed independently (Docker, VM, serverless) while
   the UI runs locally.
2. Tests for the API do not require Streamlit to be importable.
3. The UI's `APIClient` is testable with a fake HTTP session, confirming
   the actual network contract is exercised.

The cost is one extra localhost round trip per user action. On a local
dev machine this is sub-millisecond and irrelevant.
