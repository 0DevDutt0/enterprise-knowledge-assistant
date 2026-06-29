# Interview Preparation

Anticipated questions about the Enterprise Knowledge Assistant design,
with concise answers. Covers RAG fundamentals, architectural choices,
evaluation, and production concerns.

---

## RAG fundamentals

**Q: What is RAG and why use it instead of fine-tuning?**

RAG (Retrieval-Augmented Generation) adds a retrieval step before
generation: for each query, find relevant chunks from the knowledge base,
then condition the LLM on those chunks.

Fine-tuning bakes knowledge into model weights. It is expensive to
re-train when documents change, and the model can still hallucinate
without grounding. RAG is cheaper to update (reindex), produces
citations, and can refuse when retrieval finds nothing relevant.

**Q: What are the failure modes of RAG?**

1. **Retrieval failure**: the right chunk is not in the top K. The LLM
   has no grounding and hallucinates or is forced to refuse.
2. **Faithfulness failure**: the LLM ignores the retrieved context and
   answers from its parametric memory.
3. **Citation hallucination**: the LLM attributes a statement to a
   source that does not support it.
4. **Confidence miscalibration**: the system answers with high
   confidence from a weakly relevant chunk.

The confidence floor addresses (1) and (4). The prompt's citation
instructions address (2) and (3).

---

## Retrieval design

**Q: Why two retrieval stages?**

Bi-encoder retrieval (FAISS + bge-base-en-v1.5) is fast but coarse:
query and document are embedded independently so cross-attention between
them is lost. A cross-encoder (bge-reranker-base) sees query and
candidate together, catching subtle semantic matches at the cost of
running over a small candidate set (10 chunks). Two stages gives recall
from the first pass and precision from the second.

**Q: How does cosine similarity work in FAISS here?**

We use `IndexFlatIP` (inner product). By L2-normalising all vectors
before storing and before querying, inner product equals cosine
similarity. This avoids a separate normalisation call at query time.

**Q: What is `top_k_retrieval` vs `top_k_rerank`?**

`top_k_retrieval` (default 10) is how many candidates the FAISS search
returns. `top_k_rerank` (default 5) is how many survive the cross-
encoder pass. The reranker narrows from 10 to 5. The remaining 5 are
packed into the LLM prompt context.

**Q: How would you add hybrid (BM25 + dense) search?**

Add a `BM25Retriever` alongside the `FaissVectorStore`. At query time,
run both in parallel, collect their top-K lists, and fuse them using
Reciprocal Rank Fusion (RRF) before passing to the reranker. The
`RetrievalPipeline` is the right place to wire this -- it already
orchestrates the retrieval stage.

---

## Ingestion

**Q: Why element-aware chunking instead of fixed-size splitting?**

Fixed-size splits cross structural boundaries: a table split mid-row, a
heading separated from its section. The retrieved chunk must be
independently intelligible for the LLM to cite it correctly.
Element-aware chunking preserves units of meaning: tables never split,
list items stay grouped, headings travel with their first paragraph.
See `docs/adr/0002-element-aware-chunking.md`.

**Q: How do you handle scanned PDFs?**

PyMuPDF extracts the text layer of digital PDFs. If a page has no
selectable text, Tesseract OCR is called on a rasterised version of
that page. Detection is per-page so hybrid documents work correctly.
OCR can be disabled entirely via `OCR_ENABLED=false`. See ADR 0003.

**Q: How do you generate stable chunk IDs?**

Each chunk ID is a 16-hex-character prefix of the SHA-256 hash of the
chunk content and its source metadata (document path, page, element
type). This makes IDs deterministic across runs: rebuilding the index
from the same PDFs produces the same chunk IDs, which is important for
citation deduplication.

---

## Confidence and refusal

**Q: How is confidence computed?**

`confidence = 0.6 * sigmoid(avg_rerank_score) + 0.4 * top_similarity`

The rerank score is the stronger signal (60% weight). The sigmoid maps
the unbounded cross-encoder logit to (0, 1). Top similarity from the
bi-encoder provides a second opinion (40% weight). The result is
scaled to 0--100% and labelled High (>= 70%), Medium (>= 40%), or
Low (< 40%).

**Q: When does the system refuse to answer?**

When the top reranked chunk's score is strictly below `CONFIDENCE_FLOOR`
(default 0.25). In this case the LLM is never called and the canonical
refusal message is returned: "I was unable to find relevant information
in the indexed documents." The floor is configurable via `.env`.

**Q: Why a hard floor instead of asking the LLM to self-assess?**

The LLM does not know what is in the index. Asking it to assess its own
confidence based on context it just received is asking it to hallucinate
a probability. The floor is based on the retrieval signal, which is
objective (the cosine and rerank scores are computed, not generated).

---

## Evaluation

**Q: How do you measure retrieval quality?**

Retrieval precision@5: for each benchmark question, check whether at
least one of the top-5 reranked chunks comes from the expected source
document on an expected page. This is a binary hit/miss per question,
averaged over supported questions (unsupported questions are excluded
from the denominator).

**Q: How do you detect hallucination?**

Two signals:
1. `answer_must_not_contain`: if a forbidden substring appears in the
   answer, it is flagged as a hallucination.
2. `unsupported` category + non-refusal: if the system answers a
   question explicitly tagged as having no answer in the corpus, that
   is a hallucination.

These are weak proxies (keyword matching). Manual review is necessary
for production quality assurance.

**Q: What is the target for refusal rate on unsupported questions?**

100%. The system should refuse every question that has no relevant
information in the corpus. Any non-refusal on an unsupported question
is a hallucination and the most serious failure mode.

---

## Production concerns

**Q: How would you scale this beyond one machine?**

The API is stateless except for the FAISS index in `data/vector_store/`.
To scale:
1. Store the index on shared storage (NFS, S3 + local cache).
2. Deploy multiple API replicas; they share the read-only index.
3. Designate one replica (or a separate worker) to run the rebuild job
   and write the new index to shared storage.
4. After rebuild, reload the index in each replica (a hot-reload
   endpoint would trigger this).

**Q: How would you add authentication?**

Add a middleware in `app/middleware/` that validates a JWT or API key
from the `Authorization` header. The existing `CorrelationIdMiddleware`
is the pattern: it wraps the ASGI app and processes requests before they
reach the router.

For per-user document access control, the retrieval filter would need
to include a user-scoped metadata field. That requires a vector store
that supports filtered search (Qdrant, Weaviate, pgvector).

**Q: The index holds everything in memory -- what happens if it gets
corrupted?**

The FAISS index is rebuilt from the source PDFs by `POST /rebuild-index`.
The raw PDFs are the source of truth; the vector store is a derived
artifact. Losing the index file means re-running the rebuild job.

For production, the rebuild job output should be written to a versioned
location (e.g., S3 with date-stamped keys) so a previous version can
be restored if a rebuild produces bad results.

**Q: How would you log responsibly?**

The current logging policy never logs chunk text, raw document content,
query text, or generated answers -- only chunk IDs, document hashes,
and correlation IDs. This prevents PII in query text or document content
from appearing in log aggregation systems.

At `LOG_LEVEL=INFO`, only structured JSON events are emitted: request
start, stage timings, response summary. At `DEBUG`, full prompts and
retrieved chunks are logged. Never use DEBUG in production.

---

## Code and testing

**Q: How are the services tested without loading real models?**

The test suite uses `FakeEmbedder` (bag-of-words, L2-normalised) and
`FakeReranker` (word-overlap fraction) that implement the same ABCs as
the real models but require no model downloads. FastAPI is tested with
`_make_test_app()` which injects stub services without the lifespan
(no `AppComponents` created). The `APIClient` is tested with a
`_MockSession` instead of real HTTP.

**Q: Why Pydantic v2 frozen models?**

Domain models (`Chunk`, `Answer`, `Citation`) are frozen to prevent
accidental mutation in pipeline stages. A pipeline stage receives inputs
and produces outputs -- it should not modify the objects it was given.
Frozen models make this invariant enforced by the runtime.
