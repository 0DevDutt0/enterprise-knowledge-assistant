# app/ingestion/document_processing/element_classifier.py
from __future__ import annotations

import re
from collections import defaultdict

from app.models.elements import DocumentElement, ElementType

# Matches lines that open with a standard list marker.
_BULLET_RE = re.compile(
    r'^[\s]*([•\-\*·•‣◦]|\d+[.)]\s|[a-zA-Z][.)]\s)'
)
_CODE_FENCE_RE = re.compile(r'```')

# A text that appears on at least this fraction of total pages is a header/footer.
_REPEAT_THRESHOLD: float = 0.6
# Texts longer than this are never treated as headers/footers (page-number heuristic).
_MAX_HEADER_LEN: int = 200


def classify(elements: list[DocumentElement]) -> list[DocumentElement]:
    """Refine element types using cross-page and text-pattern heuristics.

    Steps applied in order:
    1. Detect texts that repeat on >= 60 % of pages -> HEADER (excluded from embeddings).
    2. Detect code fences (```) -> CODE.
    3. Detect multi-line bullet/numbered text -> LIST.
    4. Preserve all other types unchanged.
    """
    repeated = _repeated_texts(elements)
    return [_reclassify(elem, repeated) for elem in elements]


def _repeated_texts(elements: list[DocumentElement]) -> frozenset[str]:
    """Return normalized text strings that appear on >= 60 % of distinct pages."""
    all_pages = {e.page for e in elements}
    if len(all_pages) < 2:
        return frozenset()

    text_pages: dict[str, set[int]] = defaultdict(set)
    for elem in elements:
        if elem.element_type in (ElementType.HEADER, ElementType.FOOTER, ElementType.IMAGE):
            continue
        normalized = elem.text.strip().lower()
        if normalized and len(normalized) <= _MAX_HEADER_LEN:
            text_pages[normalized].add(elem.page)

    threshold = max(2, len(all_pages) * _REPEAT_THRESHOLD)
    return frozenset(t for t, pages in text_pages.items() if len(pages) >= threshold)


def _reclassify(elem: DocumentElement, repeated: frozenset[str]) -> DocumentElement:
    """Return a new DocumentElement with a refined ElementType if needed."""
    if elem.element_type in (ElementType.IMAGE, ElementType.HEADER, ElementType.FOOTER):
        return elem

    text = elem.text.strip()
    normalized = text.lower()

    if normalized in repeated:
        new_type = ElementType.HEADER
    elif _CODE_FENCE_RE.search(text):
        new_type = ElementType.CODE
    elif _is_list(text):
        new_type = ElementType.LIST
    else:
        return elem  # type unchanged; avoid creating a new object

    return DocumentElement(
        element_type=new_type,
        text=elem.text,
        page=elem.page,
        section=elem.section,
        bbox=elem.bbox,
        doc_id=elem.doc_id,
        source=elem.source,
    )


def _is_list(text: str) -> bool:
    """Return True if at least half of the non-empty lines look like list items."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    bullet_count = sum(1 for ln in lines if _BULLET_RE.match(ln))
    return bullet_count >= 2 and (bullet_count / len(lines)) >= 0.5
