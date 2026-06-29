# app/ingestion/document_processing/pdf_detector.py
from __future__ import annotations

import fitz  # PyMuPDF


def is_digital(pdf_path: str) -> bool:
    """Return True if the PDF has selectable text on at least one page.

    A PDF is considered digital when PyMuPDF can extract non-empty text from
    any page. If every page returns empty text the PDF is treated as scanned
    and OCR will be triggered by the caller.
    """
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            if page.get_text('text').strip():
                return True
        return False
    finally:
        doc.close()
