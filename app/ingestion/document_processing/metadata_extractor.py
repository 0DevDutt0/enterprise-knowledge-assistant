# app/ingestion/document_processing/metadata_extractor.py
from __future__ import annotations

import os
from datetime import datetime, timezone

from app.ingestion.document_processing.chunker import ChunkPair
from app.models.chunks import Chunk, ChunkMetadata
from app.models.elements import DocumentElement, ElementType
from app.utils.hashing import chunk_id_from_content
from app.utils.text import char_count

# Maximum length of the inferred section name stored in metadata.
_MAX_SECTION_LEN: int = 100


def annotate_elements(
    elements: list[DocumentElement],
    doc_id: str,
    source: str,
) -> list[DocumentElement]:
    """Assign section context and document provenance to each element.

    Tracks the most recent HEADING text as the current section name and
    propagates it forward to subsequent elements. Also stamps doc_id and source
    on every element so metadata_extractor.make_chunks can read them.

    Args:
        elements: Classified elements (output of element_classifier.classify).
        doc_id: Stable document identifier derived from the file path.
        source: Original file path used as the 'source' metadata field.

    Returns:
        New list of DocumentElement instances with section, doc_id, and source set.
    """
    current_section = ''
    result: list[DocumentElement] = []
    for elem in elements:
        if elem.element_type == ElementType.HEADING:
            current_section = elem.text.strip()[:_MAX_SECTION_LEN]
        result.append(DocumentElement(
            element_type=elem.element_type,
            text=elem.text,
            page=elem.page,
            section=elem.section or current_section,
            bbox=elem.bbox,
            doc_id=doc_id,
            source=source,
        ))
    return result


def make_chunks(
    pairs: list[ChunkPair],
    doc_id: str,
    source_path: str,
) -> list[Chunk]:
    """Build Chunk objects from chunker output, attaching full provenance metadata.

    Args:
        pairs: (chunk_text, source_element) tuples from chunker.chunk().
        doc_id: Stable document identifier (from hashing.doc_id_from_path).
        source_path: The original PDF path stored in Chunk.metadata.source.

    Returns:
        Fully populated Chunk objects ready to be embedded and indexed.
    """
    return [
        _make_one(text, elem, doc_id, source_path, index)
        for index, (text, elem) in enumerate(pairs)
    ]


def _make_one(
    text: str,
    source: DocumentElement,
    doc_id: str,
    source_path: str,
    index: int,
) -> Chunk:
    cid = chunk_id_from_content(doc_id, source.page, index, text)
    metadata = ChunkMetadata(
        document=os.path.basename(source_path),
        page=source.page,
        section=source.section,
        element_type=source.element_type,
        chunk_id=cid,
        source=source_path,
        char_count=char_count(text),
        created_at=datetime.now(timezone.utc),
    )
    return Chunk(text=text, metadata=metadata)
