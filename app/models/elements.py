# app/models/elements.py
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ElementType(str, Enum):
    """Document element types extracted during ingestion.

    HEADER and FOOTER are identified and excluded from embeddings.
    """

    HEADING = 'heading'
    PARAGRAPH = 'paragraph'
    TABLE = 'table'
    IMAGE = 'image'
    LIST = 'list'
    CODE = 'code'
    HEADER = 'header'
    FOOTER = 'footer'


class BoundingBox(BaseModel, frozen=True):
    """Approximate bounding box for an element on a PDF page.

    Coordinates are in PDF user-space points, origin at top-left.
    """

    x0: float
    y0: float
    x1: float
    y1: float
    page: int


class DocumentElement(BaseModel, frozen=True):
    """A single structured element extracted from a PDF.

    Produced by PyMuPDF or OCR extractors and classified by ElementClassifier
    before being passed to the chunker.
    """

    element_type: ElementType
    text: str
    page: int
    section: str = ''
    bbox: Optional[BoundingBox] = None
    doc_id: str = ''
    source: str = ''
