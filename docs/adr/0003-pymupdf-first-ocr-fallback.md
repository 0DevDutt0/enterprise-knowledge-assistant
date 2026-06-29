# ADR 0003 -- PyMuPDF-First, Tesseract Fallback

**Status:** Accepted

**Date:** 2026-06-01

---

## Context

PDF extraction can follow two strategies:

1. **OCR everything**: rasterise each page and run Tesseract. Works on
   both digital and scanned PDFs but is slow and introduces errors on
   digital PDFs.
2. **Text-layer first**: use the PDF's embedded text layer when present;
   fall back to OCR only when the text layer is absent or empty.

The corpus is expected to be predominantly digital PDFs (exported from
Word, PowerPoint, or similar tools). A minority may be scans.

---

## Decision

Use PyMuPDF (`fitz`) as the primary extractor. For each page, check
whether `Page.get_text()` returns non-empty text:

- If yes: use the PyMuPDF extraction. Do not run OCR.
- If no: run Tesseract on a rasterised version of the page.

Detection is per-page, not per-document, so hybrid documents (some
digital pages, some scanned inserts) are handled correctly.

---

## Rationale

**OCR quality.** Tesseract's character error rate on clean scans is
reasonable, but on digital PDFs it introduces capitalisation errors,
ligature confusion (`fi` -> `f1`), and hyphenation artifacts. These
corrupt embeddings because the vocabulary shifts unpredictably.

**Speed.** OCR is roughly 10-50x slower than text extraction for a
typical page. Avoiding it on digital PDFs makes ingestion fast enough
to be interactive.

**Dependency.** Tesseract is a system-level dependency that requires OS
package management. Minimising calls to it reduces the impact of
Tesseract not being installed (the system degrades gracefully: scanned
PDFs produce empty chunks with a warning instead of crashing).

---

## Consequences

- **Positive:** digital PDFs are extracted in milliseconds per page with
  zero OCR artifacts.
- **Positive:** the system still handles scanned PDFs when Tesseract is
  installed.
- **Positive:** Tesseract not being installed is handled gracefully
  (`OCR_ENABLED=false` or missing `tesseract` binary generates a log
  warning, not an exception).
- **Negative:** text-layer quality depends on the PDF producer. Some
  PDFs have broken text layers (garbled Unicode, missing spaces) that
  PyMuPDF faithfully reproduces. These are rare in standard enterprise
  documents.
- **Negative:** PDFs with both a text layer and embedded scanned images
  of different content (e.g., a legacy document with stamped signatures)
  will use the text layer. This is the correct behavior for the common
  case.
