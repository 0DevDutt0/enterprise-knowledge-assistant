# app/ingestion/document_processing/chunker.py
from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.elements import DocumentElement, ElementType

# These element types are never split; they are emitted as a single chunk.
_ATOMIC_TYPES: frozenset[ElementType] = frozenset({
    ElementType.HEADING,
    ElementType.TABLE,
    ElementType.CODE,
    ElementType.LIST,
})

# These element types are excluded from the index entirely.
_EXCLUDED_TYPES: frozenset[ElementType] = frozenset({
    ElementType.HEADER,
    ElementType.FOOTER,
    ElementType.IMAGE,
})

# Type alias for the output pair returned by chunk().
ChunkPair = tuple[str, DocumentElement]


def chunk(
    elements: list[DocumentElement],
    chunk_size: int,
    chunk_overlap: int,
) -> list[ChunkPair]:
    """Split elements into (text, source_element) pairs following SPEC rules.

    - HEADER, FOOTER, IMAGE: excluded.
    - HEADING, TABLE, CODE, LIST: emitted whole, never split.
    - PARAGRAPH (and any unrecognised type): split with
      RecursiveCharacterTextSplitter(chunk_size, chunk_overlap).

    Args:
        elements: Classified document elements from the ingestion pipeline.
        chunk_size: Maximum character count per paragraph chunk.
        chunk_overlap: Overlap in characters between consecutive paragraph chunks.

    Returns:
        List of (chunk_text, source_element) pairs ready for metadata attachment.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    pairs: list[ChunkPair] = []
    for elem in elements:
        if elem.element_type in _EXCLUDED_TYPES:
            continue

        text = elem.text.strip()
        if not text:
            continue

        if elem.element_type in _ATOMIC_TYPES:
            pairs.append((text, elem))
        else:
            for fragment in splitter.split_text(text):
                if fragment.strip():
                    pairs.append((fragment.strip(), elem))

    return pairs
