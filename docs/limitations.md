# Known Limitations

This document records known limits, caveats, and sharp edges in the
current system. It is meant to be honest, not to hedge -- these are
real constraints that matter for production use.

---

## Retrieval

### FAISS is not production-scale

The current FAISS `IndexFlatIP` is a flat index: every query is an
exhaustive linear scan over all stored vectors. This is exact and fast
for up to approximately 100k chunks (a few hundred typical PDFs) but
will become a bottleneck at larger scales.

At 1M+ chunks, a Hierarchical Navigable Small World (HNSW) or IVF index
is needed, or a dedicated vector database (Qdrant, Weaviate, pgvector).

### No filtered retrieval

FAISS does not support pre-filtering by metadata (document name, date
range, user access level) before the vector scan. All chunks in the
index compete equally for every query. If multi-tenancy or per-document
access control is required, the vector store must be replaced.

### Single index rebuild

`POST /rebuild-index` clears the existing index and re-indexes all
documents from scratch. There is no incremental add or document-level
update. On a corpus of many large documents, rebuild time can be several
minutes.

---

## Retrieval quality

### Confidence floor is heuristic

The confidence floor (default 0.25) was chosen as a reasonable default,
not calibrated against a labeled dataset. It will:
- Refuse some questions that have relevant answers in the corpus (false
  negatives) if the documents are highly technical and embedding
  similarity is low.
- Allow some hallucination-prone answers through if the corpus contains
  superficially similar but irrelevant content.

Calibrating the floor against your specific document set is recommended
before production use.

### Confidence formula is not calibrated probability

The displayed confidence percent (0--100) is derived from a sigmoid of
the rerank score blended with the top similarity score. It is a
monotonically increasing quality signal, not a calibrated probability
of being correct. Do not interpret "84%" as "84% chance the answer is
correct."

### Reranker is not fine-tuned

`bge-reranker-base` is a general-purpose cross-encoder. It performs well
on standard factual questions but may underperform on domain-specific
jargon, legal language, or highly technical numeric content without
fine-tuning.

---

## Ingestion

### OCR quality varies

Tesseract OCR works well on clean scans but degrades on:
- Low-resolution images (< 150 DPI)
- Two-column layouts with narrow gutters
- Mixed-language documents
- Handwriting

OCR-derived chunks will contain transcription errors that the reranker
cannot compensate for.

### Element classifier is heuristic

The `ElementClassifier` uses font-size thresholds for headings and regex
patterns for list items. It will misclassify:
- Documents where body text has a larger font than section headings
- Numbered paragraphs that are not list items
- Non-standard footnote or header/footer layouts

Misclassified elements are chunked as paragraphs (the safe fallback),
which usually produces acceptable results.

### No table structure preservation

Tables are stored as a single chunk containing their raw text
representation. Row-column relationships are not encoded. Retrieval can
surface the right table, but the LLM may struggle to extract a specific
cell value from unstructured table text.

### Only PDF input supported

DOCX, PPTX, HTML, and other formats are not supported. The
`VectorStore` and chunking pipeline are format-agnostic, but no
extractor exists for these file types.

---

## Generation

### Groq rate limits

The free Groq tier imposes rate limits (tokens per minute and requests
per minute). The system retries on transient errors but will return a
502 error if the rate limit is sustained. High-volume evaluation runs
may hit these limits.

### Context window budget

The prompt packs up to `MAX_CONTEXT_CHARS` (default 4000) of retrieved
text. For the `llama-3.3-70b-versatile` model the context window is
large, but very long chunks or very high `TOP_K_RERANK` values can
push total prompt length near the limit.

### Answer length is unconstrained

The LLM generates answers without an explicit length limit. Answers to
simple factual questions may be unnecessarily verbose.

---

## Evaluation

### Benchmark is authored by the project owner

The 15-question benchmark tests the question types the author
anticipated. It is a regression net, not a neutral external benchmark.
New failure modes may not be covered.

### Citation accuracy is a keyword proxy

`answer_must_contain` checks for keyword substrings in the answer text.
This catches catastrophic misses but not subtle paraphrases or
numerical rounding. Manual review is required for high-stakes accuracy
assessment.

---

## Observability

### Metrics reset on restart

In-memory `MetricsStore` (p50/p95 for `/ask` and `/rebuild-index`)
resets when the API process restarts. There is no persistent metrics
storage. For production use, export to Prometheus or a time-series
database.

### Log volume at DEBUG level

Setting `LOG_LEVEL=DEBUG` logs every retrieved chunk and the full
constructed prompt. This is useful for debugging retrieval failures
but generates significant log volume and may expose document contents
in log aggregation systems.
