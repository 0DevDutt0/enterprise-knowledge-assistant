# app/ingestion/document_processing/pymupdf_extractor.py
from __future__ import annotations

import logging

import fitz  # PyMuPDF

from app.models.elements import BoundingBox, DocumentElement, ElementType

logger = logging.getLogger(__name__)

# Font size at or above this value is provisionally classified as a heading.
# The element classifier may refine this further.
_HEADING_FONT_SIZE_THRESHOLD: float = 14.0


def extract(pdf_path: str) -> list[DocumentElement]:
    """Extract DocumentElement objects from a digital PDF using PyMuPDF.

    Assigns provisional element types:
    - Text blocks with large font -> HEADING
    - Text blocks with normal font -> PARAGRAPH
    - Image blocks -> IMAGE (text is empty)

    The element classifier refines types based on cross-page and text patterns.
    """
    elements: list[DocumentElement] = []
    doc = fitz.open(pdf_path)
    try:
        for page_num, page in enumerate(doc, start=1):
            page_dict = page.get_text('dict')
            for block in page_dict.get('blocks', []):
                elem = _block_to_element(block, page_num)
                if elem is not None:
                    elements.append(elem)
    finally:
        doc.close()

    logger.debug('pymupdf.extract path=%s elements=%d', pdf_path, len(elements))
    return elements


def _block_to_element(block: dict, page_num: int) -> DocumentElement | None:
    """Convert a single PyMuPDF block dict to a DocumentElement, or None to skip."""
    raw_bbox = block.get('bbox', (0.0, 0.0, 0.0, 0.0))
    bbox = BoundingBox(
        x0=raw_bbox[0], y0=raw_bbox[1],
        x1=raw_bbox[2], y1=raw_bbox[3],
        page=page_num,
    )

    block_type = block.get('type', 0)
    if block_type == 1:  # image block
        return DocumentElement(
            element_type=ElementType.IMAGE,
            text='',
            page=page_num,
            bbox=bbox,
        )

    # Text block
    lines = block.get('lines', [])
    text = _lines_to_text(lines)
    if not text.strip():
        return None

    max_size = _max_font_size(lines)
    elem_type = (
        ElementType.HEADING
        if max_size >= _HEADING_FONT_SIZE_THRESHOLD
        else ElementType.PARAGRAPH
    )

    return DocumentElement(
        element_type=elem_type,
        text=text,
        page=page_num,
        bbox=bbox,
    )


def _lines_to_text(lines: list[dict]) -> str:
    """Join spans within lines; join lines with newline."""
    line_texts = []
    for line in lines:
        span_text = ''.join(span.get('text', '') for span in line.get('spans', []))
        if span_text:
            line_texts.append(span_text)
    return '\n'.join(line_texts)


def _max_font_size(lines: list[dict]) -> float:
    """Return the largest font size found across all spans, or 0.0 if none."""
    sizes = [
        span.get('size', 0.0)
        for line in lines
        for span in line.get('spans', [])
        if span.get('size', 0.0)
    ]
    return max(sizes, default=0.0)
