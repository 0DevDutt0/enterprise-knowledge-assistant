# ADR 0002 -- Element-Aware Chunking

**Status:** Accepted

**Date:** 2026-06-01

---

## Context

Chunking strategy directly determines retrieval quality. The two common
approaches are:

1. **Naive fixed-size chunking**: split raw text every N characters
   with overlap. Simple to implement; destroys document structure.
2. **Element-aware chunking**: detect document structure first, then
   apply per-element-type chunking rules.

The corpus consists of enterprise PDFs with rich structure: section
headings, numbered lists, tables, code blocks in technical manuals.

---

## Decision

Implement element-aware chunking:

1. Extract raw blocks from the PDF (via PyMuPDF or Tesseract).
2. Classify each block as one of: `HEADING`, `PARAGRAPH`, `TABLE`,
   `LIST_ITEM`, `CODE`, `HEADER`, `FOOTER`, `CAPTION`, `OTHER`.
3. Apply type-specific rules:
   - `TABLE`, `CODE`: store as one chunk, never split.
   - `HEADING`: merge with following content if total <= chunk_size.
   - `LIST_ITEM`: group consecutive list items into one chunk.
   - `PARAGRAPH`: split with `RecursiveCharacterTextSplitter` at
     800 chars / 150 overlap.
   - `HEADER`, `FOOTER`: discard (repeated boilerplate).

---

## Rationale

**Retrievable unit of meaning.** A table split mid-row is not a useful
retrieval result. A heading without its section body is not either. The
system returns chunks to the LLM, and each chunk must stand alone.

**Empirical observation.** In the benchmark (see `EVALUATION.md`),
retrieval precision on multi-hop questions -- which often require
matching a table cell or list item -- was substantially higher with
element-aware chunking than with fixed-size splitting in internal tests.

**Graceful degradation.** Anything the classifier cannot identify
becomes `PARAGRAPH` and is chunked normally. The downside of a
misclassification is a slightly worse chunk boundary, not a crash.

---

## Consequences

- **Positive:** retrieved chunks are almost always independently
  intelligible.
- **Positive:** tables and code blocks are never corrupted by splits.
- **Negative:** the classifier is heuristic and will misclassify
  unusual layouts. See `docs/limitations.md`.
- **Negative:** more complex ingestion pipeline than naive splitting.
  Justified by the measurable retrieval quality improvement.
- **Neutral:** chunk sizes are variable (small headings, large tables).
  The prompt builder handles this with a character-budget guard.
