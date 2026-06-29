# ADR 0001 -- FAISS as the Vector Store

**Status:** Accepted

**Date:** 2026-06-01

---

## Context

The system needs a vector store that can:
- Accept dense float32 embeddings for ~100k chunks
- Return approximate top-K neighbours with similarity scores
- Persist to disk and reload at startup
- Run without an external service

Candidates evaluated: FAISS, Chroma, Qdrant, pgvector.

---

## Decision

Use `faiss-cpu` with `IndexFlatIP` (inner product) over L2-normalised
vectors (equivalent to cosine similarity).

---

## Rationale

**No external service dependency.** Qdrant and Weaviate require a
separate running container. Chroma has an embedded mode but adds a
~200 MB dependency with SQLite state management. FAISS is a single
C++ library wrapped in Python with no runtime daemon.

**Exact search is fast enough.** At the target scale (a few hundred
enterprise PDFs, at most 50k chunks), `IndexFlatIP` exhaustive search
completes in under 10ms on CPU. Approximate methods (IVF, HNSW) trade
recall for speed -- a trade that is not needed here.

**Single-file persistence.** `faiss.write_index` / `faiss.read_index`
writes the complete index as a binary file. This maps well to the
project's requirement that the vector store is a build artifact, not
a running service.

**Wrapped behind an interface.** `VectorStore` is an ABC. Swapping to
Qdrant or pgvector is a one-file change in `app/rag/retrieval/`.

---

## Consequences

- **Positive:** zero infrastructure to run for local development.
- **Negative:** no filtered search (by document, date, user). This
  rules out multi-tenancy without a store replacement.
- **Negative:** at 1M+ chunks, a flat index becomes a bottleneck.
  Accepted as out of scope for this project.
- **Negative:** concurrent writes are unsafe. The current design has
  only one writer (the IndexingService) and treats rebuild as a
  serialised operation.
