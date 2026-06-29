# app/ui/components/answer_card.py
from __future__ import annotations

import streamlit as st

from app.ui.components.confidence_badge import confidence_badge_html
from app.ui.components.source_card import source_cards_html

# Warning triangle for the refusal card
_REFUSAL_ICON = (
    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"'
    ' xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;margin-top:2px;">'
    '<path d="M8 2.5L13.5 12.5H2.5L8 2.5z" stroke="#D97706" stroke-width="1.3"'
    ' stroke-linejoin="round" fill="none"/>'
    '<path d="M8 6.5v3" stroke="#D97706" stroke-width="1.3" stroke-linecap="round"/>'
    '<circle cx="8" cy="11" r="0.75" fill="#D97706"/>'
    '</svg>'
)


def render_answer(response: dict) -> None:
    """Render the answer card and source citations for a /ask API response.

    Handles both grounded answers and canonical refusals. Grounded answers
    are rendered with a left-accent card, confidence badge, processing time,
    and a citations grid. Refusals are rendered with an amber warning card.

    Args:
        response: Parsed JSON dict from POST /ask.
    """
    is_refusal = response.get('is_refusal', False)
    answer_text = response.get('answer', '')
    citations = response.get('citations', [])
    band = response.get('confidence_band', 'Low')
    pct = float(response.get('confidence_percent', 0.0))
    elapsed = float(response.get('processing_time_ms', 0.0))

    if is_refusal:
        st.markdown(
            f'<div class="eka-refusal">'
            f'<div style="display:flex;align-items:flex-start;gap:10px;">'
            f'{_REFUSAL_ICON}'
            f'<div>'
            f'<strong style="display:block;margin-bottom:4px;">No relevant content found</strong>'
            f'{answer_text}'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    badge_html = confidence_badge_html(band, pct)
    elapsed_label = f'{elapsed / 1000:.2f}s' if elapsed >= 1000 else f'{elapsed:.0f} ms'
    time_html = f'<span class="eka-meta-time">{elapsed_label}</span>'
    citation_count = len(citations)
    cit_label = (
        f'<span class="eka-meta-time">'
        f'{citation_count} source{"s" if citation_count != 1 else ""}'
        f'</span>'
        if citation_count
        else ''
    )

    card_html = (
        f'<div class="eka-answer-wrapper">'
        f'<div class="eka-card">'
        f'<p class="eka-card-label">Answer</p>'
        f'<p class="eka-answer-text">{answer_text}</p>'
        f'<div class="eka-meta-row">'
        f'{badge_html}'
        f'&ensp;{time_html}'
        f'{"&ensp;" + cit_label if cit_label else ""}'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)

    if citations:
        _render_citations(citations)


def _render_citations(citations: list[dict]) -> None:
    """Render the source citation grid below the answer card."""
    st.markdown(
        '<p class="eka-sources-heading">Sources</p>',
        unsafe_allow_html=True,
    )
    st.markdown(source_cards_html(citations), unsafe_allow_html=True)
