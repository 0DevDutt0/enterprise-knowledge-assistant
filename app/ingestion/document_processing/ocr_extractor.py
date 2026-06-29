# app/ingestion/document_processing/ocr_extractor.py
from __future__ import annotations

import io
import logging

import fitz  # PyMuPDF
from PIL import Image

from app.models.elements import DocumentElement, ElementType

logger = logging.getLogger(__name__)

# Render scale for OCR: 2x gives ~144 dpi which balances quality vs memory.
_RENDER_SCALE: int = 2


def extract(pdf_path: str, tesseract_cmd: str = '') -> list[DocumentElement]:
    """Extract DocumentElement objects from a scanned PDF using Tesseract OCR.

    If Tesseract is not installed or cannot be invoked, logs a warning and
    returns an empty list instead of raising. This matches the SPEC requirement
    that OCR failure degrades gracefully.

    Each page becomes a single PARAGRAPH element. Fine-grained element typing
    (headings, lists) is left to the element classifier when text patterns allow.
    """
    import pytesseract  # imported here to defer the Tesseract dependency check

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        logger.warning('ocr.tesseract_unavailable reason=%s', exc)
        return []

    elements: list[DocumentElement] = []
    doc = fitz.open(pdf_path)
    try:
        mat = fitz.Matrix(_RENDER_SCALE, _RENDER_SCALE)
        for page_num, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes('png')))
            text: str = pytesseract.image_to_string(img)
            if text.strip():
                elements.append(DocumentElement(
                    element_type=ElementType.PARAGRAPH,
                    text=text.strip(),
                    page=page_num,
                ))
    finally:
        doc.close()

    logger.debug('ocr.extract path=%s elements=%d', pdf_path, len(elements))
    return elements
