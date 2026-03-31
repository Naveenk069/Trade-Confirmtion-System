"""
page_recommender.py — Smart Template Recommender with Confidence Scores (P3).

When a user uploads or describes a trade, the system:
1. Runs semantic search to find the top 3 most similar templates
2. For each result, computes a confidence score with explanation
3. Shows WHY each template was recommended (matched fields)
4. Lets user pick one and jump straight to Generate or Diff
"""

import streamlit as st
import requests
import html as _html
from src.auth import log_audit

API_BASE = "http://localhost:8000"

CONFIDENCE_RULES = [
    ("trade_type",    0.35, "Trade type match"),
    ("jurisdiction",  0.20, "Jurisdiction match"),
    ("currency",      0.15, "Currency match"),
    ("counterparty",  0.15, "Counterparty match"),
    ("product",       0.15, "Product category match"),
]


def _api_post(path, payload):
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _api_get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _confidence_score(result: dict, trade_inputs: dict) -> tuple[float, list]:
    """
    Compute explainable confidence score 0–100.
    Returns (score, reasons_list).
    """
    score   = 0.0
    reasons = []

    semantic = result.get("score", 0) * 40  # up to 40 pts from semantic similarity
    score += semantic
    reasons.append({
        "label": "Semantic similarity",
        "pts":   semantic,
        "max":   40,
        "match": True,
    })

    for field, weight, label in CONFIDENCE_RULES:
        input_val  = trade_inputs.get(field, "").lower().strip()
        result_val = str(result.get(field, "")).lower().strip()
        if input_val and result_val and (
            input_val in result_val or result_val in input_val
        ):
            pts = weight * 60
            score += pts
            reasons.append({"label": label, "pts": pts,
                             "max": weight*60, "match": True})
        elif input_val:
            reasons.append({"label": label, "pts": 0,
                             "max": weight*60, "match": False})

    return min(100.0, score), reasons


def _confidence_bar(score: float) -> str:
    col = "#ff5050" if score < 40 else "#fbbf24" if score < 70 else "#00ff88"
    pct = int(score)
    return (
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<div style="flex:1;height:6px;background:rgba(255,255,255,0.08);border-radius:3px;">'
        f'<div style="width:{pct}%;height:100%;background:{col};border-radius:3px;'
        f'transition:width 0.4s;"></div></div>'
        f'<span style="font-size:13px;font-weight:800;color:{col};min-width:36px;">'
        f'{pct}%</span></div>'
    )


def _reason_chip(reason: dict) -> str:
    if reason["match"]:
        return (f'<span style="display:inline-block;padding:3px 10px;margin:2px;'
                f'border-radius:20px;font-size:10px;font-weight:600;'
                f'background:rgba(0,255,136,0.1);color:#00ff88;'
                f'border:1px solid rgba(0,255,136,0.25);">✓ {reason["label"]}'
                f'&nbsp;<span style="opacity:0.6">+{reason["pts"]:.0f}pts</span></span>')
    else:
        return (f'<span style="display:inline-block;padding:3px 10px;margin:2px;'
                f'border-radius:20px;font-size:10px;font-weight:600;'
                f'background:rgba(255,255,255,0.03);color:rgba(255,255,255,0.3);'
                f'border:1px solid rgba(255,255,255,0.08);">✗ {reason["label"]}</span>')


def page_recommender():
    st.markdown(
        '<div class="page-header">'
        '<div class="page-title">Smart <span>Recommender</span></div>'
        '<div class="page-subtitle">Describe your trade — AI finds the best matching templates with confidence scores and explanations</div>'
        '</div>',
        unsafe_allow_html=True
    )

    username = st.session_state.get("user", {}).get("username", "unknown")

    # ── Input panel ────────────────────────────────────────────────────────
    st.markdown(
        '<div style="background:rgba(0,212,255,0.04);border:1px solid rgba(0,212,255,0.12);'
        'border-radius:14px;padding:22px 26px;margin-bottom:20px;">',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div style="font-size:13px;font-weight:700;color:#00D4FF;margin-bottom:14px;">'
        '📋 Describe Your Trade</div>',
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)
    with c1:
        query       = st.text_input("Search Query",
                                    placeholder='e.g. "Goldman Sachs USD interest rate swap 5 year"',
                                    key="rec_query")
        trade_type  = st.selectbox("Trade Type",
                                   ["", "Interest Rate Swap", "FX Forward",
                                    "Credit Default Swap", "Equity Swap"],
                                   key="rec_tt")
        currency    = st.selectbox("Currency",
                                   ["", "USD", "GBP", "EUR", "JPY", "CHF"],
                                   key="rec_cur")
    with c2:
        counterparty = st.text_input("Counterparty",
                                     placeholder='e.g. "Goldman Sachs"',
                                     key="rec_cp")
        jurisdiction = st.selectbox("Jurisdiction",
                                    ["", "US", "UK", "EU", "APAC"],
                                    key="rec_jur")
        product      = st.selectbox("Product",
                                    ["", "IRS", "FX", "CDS", "Equity"],
                                    key="rec_prod")

    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🔍  Find Best Templates", key="rec_search",
                 use_container_width=True):
        if not query.strip():
            st.markdown(
                '<div class="alert alert-warn">⚠ Please enter a search query.</div>',
                unsafe_allow_html=True
            )
        else:
            trade_inputs = {
                "trade_type":  trade_type,
                "currency":    currency,
                "counterparty":counterparty,
                "jurisdiction":jurisdiction,
                "product":     product,
            }

            payload = {"query": query, "top_k": 5, "active_only": True}
            if trade_type:  payload["trade_type"]  = trade_type
            if jurisdiction: payload["jurisdiction"] = jurisdiction
            if product:     payload["product"]      = product

            with st.spinner("Searching and scoring templates…"):
                result = _api_post("/search", payload)

            log_audit(username, "SEARCH",
                      f"Recommender: {query[:60]}")

            if not result or "error" in result:
                st.markdown(
                    '<div class="alert alert-error">❌ Search failed. Is the API running?</div>',
                    unsafe_allow_html=True
                )
            elif result.get("total_results", 0) == 0:
                st.markdown(
                    '<div class="alert alert-info">💡 No matching templates found. '
                    'Try broader search terms.</div>',
                    unsafe_allow_html=True
                )
            else:
                st.session_state["rec_results"]      = result["results"]
                st.session_state["rec_trade_inputs"] = trade_inputs
                st.session_state["rec_query_text"]   = query

    # ── Results ────────────────────────────────────────────────────────────
    results = st.session_state.get("rec_results", [])
    if not results:
        return

    trade_inputs = st.session_state.get("rec_trade_inputs", {})
    query_text   = st.session_state.get("rec_query_text", "")

    st.markdown(
        f'<div style="font-size:12px;color:rgba(255,255,255,0.35);'
        f'margin:16px 0 8px;">Top {len(results)} recommendations for: '
        f'<b style="color:#00D4FF">{_html.escape(query_text)}</b></div>',
        unsafe_allow_html=True
    )

    for i, r in enumerate(results):
        conf, reasons = _confidence_score(r, trade_inputs)
        matched = sum(1 for rr in reasons if rr["match"])
        total_r = len(reasons)

        conf_col = "#ff5050" if conf < 40 else "#fbbf24" if conf < 70 else "#00ff88"
        rank_label = ["🥇 Best Match", "🥈 Second Match", "🥉 Third Match",
                      "4th Match", "5th Match"][i]

        # Card
        st.markdown(
            f'<div style="background:#0D1B35;border:1px solid rgba(255,255,255,0.08);'
            f'border-left:4px solid {conf_col};border-radius:14px;'
            f'padding:20px 24px;margin-bottom:16px;">',
            unsafe_allow_html=True
        )

        # Header row
        st.markdown(
            f'<div style="display:flex;align-items:center;'
            f'justify-content:space-between;margin-bottom:10px;">'
            f'<div>'
            f'<span style="font-size:11px;font-weight:700;color:rgba(255,255,255,0.3);">'
            f'{rank_label}</span>'
            f'<div style="font-size:14px;font-weight:700;color:#fff;margin-top:2px;">'
            f'📄 {_html.escape(r["filename"])}</div>'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<div style="font-size:10px;color:rgba(255,255,255,0.3);margin-bottom:4px;">'
            f'Confidence Score</div>'
            f'<div style="font-size:28px;font-weight:900;color:{conf_col};">'
            f'{conf:.0f}%</div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

        # Confidence bar
        st.markdown(_confidence_bar(conf), unsafe_allow_html=True)

        # Reason chips
        chips = "".join(_reason_chip(rr) for rr in reasons)
        st.markdown(
            f'<div style="margin:10px 0 8px;">{chips}</div>',
            unsafe_allow_html=True
        )

        # Metadata badges
        cp_short = r["counterparty"].split(" and ")[0][:35]
        st.markdown(
            f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">'
            f'<span class="badge badge-trade">⚡ {_html.escape(r["trade_type"])}</span>'
            f'<span class="badge badge-cp">🏦 {_html.escape(cp_short)}</span>'
            f'<span class="badge badge-jur">🌍 {_html.escape(r["jurisdiction"])}</span>'
            f'<span class="badge badge-prod">📦 {_html.escape(r["product"])}</span>'
            f'<span class="badge badge-ver">v{_html.escape(str(r["version"]))}</span>'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.3);">'
            f'Semantic: {r["score"]:.3f} &nbsp;·&nbsp; '
            f'{matched}/{total_r} criteria matched</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Action buttons
        ba, bb, bc = st.columns([1.5, 1.5, 4])
        with ba:
            if st.button("🚀 Use for Generation",
                         key=f"rec_gen_{i}", use_container_width=True):
                st.session_state.page = "generate"
                st.session_state["prefill_template_id"] = r["doc_id"]
                st.session_state["prefill_trade_type"]  = r["trade_type"]
                log_audit(username, "GENERATE",
                          f"Recommender → Generate: {r['filename']}")
                st.rerun()
        with bb:
            if st.button("⚡ Compare with Diff",
                         key=f"rec_diff_{i}", use_container_width=True):
                st.session_state.page = "diff"
                log_audit(username, "DIFF",
                          f"Recommender → Diff: {r['filename']}")
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
