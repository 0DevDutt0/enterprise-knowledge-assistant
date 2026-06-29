# app/ingestion/pipeline.py
from __future__ import annotations

import logging

from app.config.settings import Settings
from app.ingestion.document_processing import (
    chunker,
    element_classifier,
    metadata_extractor,
    ocr_extractor,
    pdf_detector,
    pymupdf_extractor,
)
from app.models.chunks import Chunk
from app.utils.hashing import doc_id_from_path
from app.utils.timing import timed

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates the full ingestion flow: PDF path -> list[Chunk].

    Steps:
    1. Detect whether the PDF is digital or scanned.
    2. Extract DocumentElement objects (PyMuPDF or Tesseract OCR).
    3. Classify element types (heading/list/code/header detection).
    4. Annotate with section context and document provenance.
    5. Chunk according to per-type rules.
    6. Attach full metadata to produce Chunk objects.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(self, pdf_path: str) -> list[Chunk]:
        """Process a PDF file and return a list of embedded-ready Chunk objects.

        Args:
            pdf_path: Absolute or repo-relative path to the PDF.

        Returns:
            list[Chunk] ready to be passed to the Embedder.
        """
        doc_id = doc_id_from_path(pdf_path)

        with timed('pdf_detect', logger):
            digital = pdf_detector.is_digital(pdf_path)

        if digital:
            logger.info('ingestion.digital doc_id=%s', doc_id)
            with timed('extract_pymupdf', logger):
                elements = pymupdf_extractor.extract(pdf_path)
        elif self._settings.ocr_enabled:
            logger.info('ingestion.ocr doc_id=%s', doc_id)
            with timed('extract_ocr', logger):
                elements = ocr_extractor.extract(
                    pdf_path,
                    tesseract_cmd=self._settings.tesseract_cmd,
                )
        else:
            logger.warning('ingestion.ocr_disabled doc_id=%s', doc_id)
            elements = []

        with timed('classify', logger):
            elements = element_classifier.classify(elements)

        with timed('annotate', logger):
            elements = metadata_extractor.annotate_elements(
                elements, doc_id=doc_id, source=pdf_path
            )

        with timed('chunk', logger):
            pairs = chunker.chunk(
                elements,
                chunk_size=self._settings.chunk_size,
                chunk_overlap=self._settings.chunk_overlap,
            )

        with timed('make_chunks', logger):
            chunks = metadata_extractor.make_chunks(pairs, doc_id, pdf_path)

        logger.info('ingestion.complete doc_id=%s chunks=%d', doc_id, len(chunks))
        return chunks
