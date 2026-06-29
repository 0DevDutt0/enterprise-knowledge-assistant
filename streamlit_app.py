# streamlit_app.py
from __future__ import annotations

import streamlit as st

from app.ui.styles import inject_styles

# Document + search icon (geometric, clean)
_LOGO_SVG = (
    '<svg width="28" height="28" viewBox="0 0 28 28" fill="none"'
    ' xmlns="http://www.w3.org/2000/svg">'
    '<rect width="28" height="28" rx="7" fill="#0369A1"/>'
    '<path d="M8 7h8l4 4v10H8V7z" fill="white" fill-opacity="0.2"/>'
    '<path d="M16 7v4h4" fill="none" stroke="white" stroke-width="1.5"'
    ' stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M8 7h8l4 4v10H8V7z" fill="none" stroke="white" stroke-width="1.5"'
    ' stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="13" cy="16" r="2.5" stroke="white" stroke-width="1.5"/>'
    '<path d="M15 18l2 2" stroke="white" stroke-width="1.5" stroke-linecap="round"/>'
    '</svg>'
)

_SIDEBAR_BRAND = (
    '<div style="padding:20px 16px 16px 16px;">'
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">'
    '{logo}'
    '<div>'
    '<p style="font-size:0.875rem;font-weight:700;color:#F8FAFC;'
    'margin:0;letter-spacing:-0.01em;line-height:1.2;">Knowledge</p>'
    '<p style="font-size:0.875rem;font-weight:700;color:#F8FAFC;'
    'margin:0;letter-spacing:-0.01em;line-height:1.2;">Assistant</p>'
    '</div>'
    '</div>'
    '<p style="font-size:0.6875rem;color:#475569;margin:0;letter-spacing:0.02em;">'
    'Enterprise RAG &middot; v1.0'
    '</p>'
    '</div>'
).format(logo=_LOGO_SVG)

_SIDEBAR_ABOUT = (
    '<div style="padding:4px 16px 16px 16px;">'
    '<p style="font-size:0.625rem;font-weight:700;letter-spacing:0.12em;'
    'text-transform:uppercase;color:#334155;margin:0 0 8px 0;">About</p>'
    '<p style="font-size:0.8rem;color:#475569;line-height:1.6;margin:0;">'
    'RAG over indexed PDFs &mdash; grounded answers with citations.'
    '</p>'
    '</div>'
)

_SIDEBAR_FOOTER = (
    '<div style="padding:12px 16px;margin-top:8px;border-top:1px solid #1E293B;">'
    '<p style="font-size:0.625rem;font-weight:700;letter-spacing:0.12em;'
    'text-transform:uppercase;color:#334155;margin:0 0 8px 0;">Index</p>'
    '<p style="font-size:0.75rem;color:#475569;margin:0 0 10px 0;line-height:1.5;">'
    'Place PDFs in <code style="font-size:0.7rem;background:rgba(255,255,255,0.07);'
    'color:#7DD3FC;padding:1px 4px;border-radius:3px;">data/raw/</code>'
    ' then rebuild.'
    '</p>'
    '<div style="display:flex;align-items:center;gap:7px;">'
    '<span style="width:7px;height:7px;background:#22C55E;border-radius:50%;'
    'display:inline-block;flex-shrink:0;"></span>'
    '<span style="font-size:0.75rem;color:#475569;font-weight:500;">API connected</span>'
    '</div>'
    '</div>'
)


def main() -> None:
    """Entry point for the Streamlit Knowledge Assistant UI."""
    st.set_page_config(
        page_title='Knowledge Assistant',
        page_icon=':page_with_curl:',
        layout='centered',
        initial_sidebar_state='expanded',
        menu_items=None,
    )
    inject_styles()

    with st.sidebar:
        st.markdown(_SIDEBAR_BRAND, unsafe_allow_html=True)
        st.markdown('<hr style="border-color:#1E293B;margin:0 0 8px 0;">', unsafe_allow_html=True)
        st.markdown(_SIDEBAR_ABOUT, unsafe_allow_html=True)
        st.markdown(_SIDEBAR_FOOTER, unsafe_allow_html=True)

    from app.ui.pages.ask import render
    render()


if __name__ == '__main__':
    main()
