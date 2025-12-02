# asf_app/ui/theme.py
# -*- coding: utf-8 -*-
"""
Gestion du thème global Streamlit.

Un simple flag ON/OFF permet de basculer sur un thème modernisé
ou de rester sur l’apparence actuelle.
"""

import streamlit as st


CSS_BASE = """
<style>
div.stButton > button[kind="primary"],
div.stButton > button[kind="secondary"] {
    background-color: #e5e7eb !important;
    color: #222 !important;
    border: 1px solid #d7dce5 !important;
    border-radius: 10px !important;
    padding: 0.5rem 0.9rem !important;
}
</style>
"""

CSS_MODERN = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500&display=swap');
:root {
    --asf-bg: radial-gradient(circle at 20% 20%, #fdf2f8 0%, #f8fafc 30%, #eef2ff 65%, #e0f2fe 100%);
    --asf-card: #ffffff;
    --asf-border: #d5d9e2;
    --asf-text: #0f172a;
    --asf-muted: #475569;
    --asf-accent: #2563eb;      /* bleu électrique */
    --asf-accent-2: #ef4444;    /* corail/rouge doux */
    --asf-accent-3: #14b8a6;    /* turquoise */
    --asf-radius: 14px;
    --asf-shadow: 0 15px 50px rgba(37, 99, 235, 0.12);
}
[data-testid="stAppViewContainer"] {
    background: var(--asf-bg);
}
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
h1, h2, h3, h4, h5, h6 {
    font-family: 'Space Grotesk', 'Inter', sans-serif;
    color: var(--asf-text);
    letter-spacing: -0.01em;
}
body, .stMarkdown, .stText, .stDataFrame {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    color: var(--asf-text);
}
div.stButton > button {
    background: linear-gradient(120deg, #e5e7eb, #f8fafc) !important;
    color: var(--asf-text) !important;
    border: 1px solid var(--asf-border) !important;
    border-radius: 12px !important;
    padding: 0.6rem 1rem !important;
    box-shadow: 0 3px 10px rgba(0,0,0,0.06);
    transition: all 0.15s ease;
}
div.stButton > button:hover {
    background: linear-gradient(120deg, #e0e7ff, #e2e8f0) !important;
    transform: translateY(-1px);
}
div[data-testid="stExpander"] {
    border: 1px solid var(--asf-border);
    border-radius: var(--asf-radius);
    background: var(--asf-card);
    box-shadow: var(--asf-shadow);
}
div[data-testid="stVerticalBlock"] {
    background: var(--asf-card);
    border: 1px solid var(--asf-border);
    border-radius: var(--asf-radius);
    padding: 1rem;
    box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
}
table {
    border-collapse: collapse !important;
}
thead tr th {
    background: linear-gradient(90deg, rgba(37,99,235,0.12), rgba(20,184,166,0.12)) !important;
    color: var(--asf-text) !important;
    font-weight: 700;
    border-bottom: 1px solid var(--asf-border) !important;
}
tbody tr:nth-child(even) {
    background: #f8fafc !important;
}
.stDataFrame table {
    border: 1px solid var(--asf-border) !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 0.6rem;
}
.stTabs [data-baseweb="tab"] {
    background: rgba(255,255,255,0.7);
    color: var(--asf-muted);
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 0.45rem 0.9rem;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    border: 1px solid var(--asf-border);
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.15);
    color: var(--asf-text);
}
.stSelectbox > div, .stMultiSelect > div, .stTextInput > div, .stNumberInput > div {
    border-radius: 12px;
    border: 1px solid var(--asf-border);
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.stDataFrame [role="columnheader"] {
    font-weight: 700;
}
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #93c5fd, #6ee7b7);
    border-radius: 10px;
}
</style>
"""


def apply_theme(use_modern: bool) -> None:
    """
    Applique le thème modernisé si use_modern=True,
    sinon applique seulement le style minimal des boutons (CSS_BASE).
    """
    if use_modern:
        st.markdown(CSS_MODERN, unsafe_allow_html=True)
    else:
        st.markdown(CSS_BASE, unsafe_allow_html=True)
