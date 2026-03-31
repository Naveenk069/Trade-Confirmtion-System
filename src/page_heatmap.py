"""
page_heatmap.py — Risk Heatmap Dashboard (P2 Feature).

Shows:
- Heatmap grid: counterparty × field — colour = avg risk score
- Top 5 highest-risk field changes across all sessions
- Avg risk score trend (session history)
- Most-changed fields bar chart
All powered by audit log + in-session diff history stored in session_state.
"""

import streamlit as st
import requests
import json
import time
from collections import defaultdict
from src.auth import get_audit_logs, log_audit

API_BASE = "http://localhost:8000"

HEATMAP_CSS = """
<style>
.hm-grid { display: grid; gap: 4px; margin: 16px 0; }
.hm-cell {
    border-radius: 6px; padding: 8px 6px;
    font-size: 10px; font-weight: 700;
    text-align: center; cursor: default;
    transition: transform 0.15s;
}
.hm-cell:hover { transform: scale(1.08); z-index: 10; }
.hm-header {
    font-size: 10px; color: rgba(255,255,255,0.35);
    font-weight: 600; text-align: center;
    letter-spacing: 0.5px; padding: 4px;
    white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis;
}
.hm-row-label {
    font-size: 11px; color: rgba(255,255,255,0.5);
    font-weight: 600; padding: 8px 4px;
    white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; display: flex;
    align-items: center;
}
.stat-bar-wrap {
    background: rgba(255,255,255,0.05);
    border-radius: 4px; height: 8px;
    overflow: hidden; margin-top: 4px;
}
.stat-bar-fill {
    height: 100%; border-radius: 4px;
    transition: width 0.4s ease;
}
.hm-legend {
    display: flex; gap: 6px; align-items: center;
    font-size: 10px; color: rgba(255,255,255,0.3);
    margin-bottom: 12px;
}
.hm-legend-grad {
    width: 120px; height: 10px; border-radius: 4px;
    background: linear-gradient(90deg, #00ff88, #fbbf24, #ff5050);
}
</style>
"""

def _score_to_color(score: float) -> str:
    """0–100 → green → amber → red hex."""
    score = max(0.0, min(100.0, score))
    if score < 30:
        r = int(score / 30 * 245)
        return f"#{r:02x}ff{0:02x}"
    elif score < 60:
        t = (score - 30) / 30
        r = int(245 + t * 10)
        g = int(255 - t * 100)
        return f"#{min(255,r):02x}{max(0,g):02x}0b"
    else:
        t = (score - 60) / 40
        g = int(155 - t * 155)
        return f"#ff{g:02x}50"

def _text_color(score: float) -> str:
    return "#000" if score < 50 else "#fff"

def _api_get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def _api_post(path, payload):
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _load_diff_history() -> list:
    """Load diff history from session state."""
    return st.session_state.get("diff_history", [])

def _store_diff(diff_result: dict):
    if "diff_history" not in st.session_state:
        st.session_state.diff_history = []
    st.session_state.diff_history.append({
        "timestamp": time.time(),
        "template":  diff_result.get("template_filename", ""),
        "incoming":  diff_result.get("incoming_filename", ""),
        "score":     diff_result.get("risk_score", 0),
        "high":      diff_result.get("high_risk_count", 0),
        "discrepancies": diff_result.get("discrepancies", []),
    })

def page_heatmap():
    st.markdown(HEATMAP_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="page-header">'
        '<div class="page-title">Risk <span>Heatmap</span></div>'
        '<div class="page-subtitle">Visual risk analysis across counterparties and fields — run comparisons to populate</div>'
        '</div>',
        unsafe_allow_html=True
    )

    username = st.session_state.get("user", {}).get("username", "unknown")

    # ── Quick Compare to populate heatmap ─────────────────────────────────
    with st.expander("⚡ Run a Quick Comparison to add data", expanded=False):
        data = _api_get("/templates?active_only=false")
        templates = data.get("templates", []) if data else []
        if templates:
            options = {f"{t['filename']}": t["doc_id"] for t in templates}
            c1, c2 = st.columns(2)
            with c1:
                sel_a = st.selectbox("Reference", list(options.keys()), key="hm_a")
            with c2:
                sel_b = st.selectbox("Incoming",  list(options.keys()), key="hm_b")
            if st.button("Compare & Add to Heatmap", key="hm_run"):
                with st.spinner("Computing diff…"):
                    result = _api_post("/diff/compare", {
                        "template_doc_id": options[sel_a],
                        "incoming_doc_id": options[sel_b],
                    })
                if result and "error" not in result:
                    _store_diff(result)
                    log_audit(username, "DIFF", f"Heatmap: {sel_a} vs {sel_b}")
                    st.success("Added to heatmap!")
                    st.rerun()

    history = _load_diff_history()

    if not history:
        # Show demo heatmap with synthetic data
        st.markdown("""<div style="background:rgba(0,212,255,0.05);border:1px solid
            rgba(0,212,255,0.15);border-radius:12px;padding:18px 22px;margin:16px 0;">
            <div style="font-size:13px;font-weight:700;color:#00D4FF;margin-bottom:6px;">
                No comparison data yet</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.4);">
                Use the expander above to run comparisons.
                Each comparison adds a data point to the heatmap.
            </div>
        </div>""", unsafe_allow_html=True)
        _render_demo_heatmap()
        return

    # ── Stats row ──────────────────────────────────────────────────────────
    total_runs  = len(history)
    avg_score   = sum(h["score"] for h in history) / total_runs
    max_score   = max(h["score"] for h in history)
    total_high  = sum(h["high"] for h in history)
    sc_col = "#ff5050" if avg_score >= 50 else "#fbbf24" if avg_score >= 20 else "#00ff88"

    st.markdown(f"""<div class="metric-row">
        <div class="metric-card mc-cyan">
            <div class="metric-icon">🔀</div>
            <div class="metric-value">{total_runs}</div>
            <div class="metric-label">Comparisons Run</div>
        </div>
        <div class="metric-card mc-amber">
            <div class="metric-icon">📊</div>
            <div class="metric-value" style="color:{sc_col}">{avg_score:.0f}</div>
            <div class="metric-label">Avg Risk Score</div>
        </div>
        <div class="metric-card mc-purple">
            <div class="metric-icon">⚠</div>
            <div class="metric-value">{max_score:.0f}</div>
            <div class="metric-label">Peak Risk Score</div>
        </div>
        <div class="metric-card mc-red" style="background:rgba(255,80,80,0.08);
            border:1px solid rgba(255,80,80,0.2);">
            <div class="metric-icon">🔴</div>
            <div class="metric-value" style="color:#ff5050">{total_high}</div>
            <div class="metric-label">HIGH Risk Changes</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Field risk frequency ───────────────────────────────────────────────
    field_risk: dict = defaultdict(list)
    for h in history:
        for d in h.get("discrepancies", []):
            risk_score = {"HIGH": 80, "MEDIUM": 40, "LOW": 10}.get(d.get("risk_level", "LOW"), 10)
            field_risk[d.get("field_key", "unknown")].append(risk_score)

    if field_risk:
        st.markdown('<div style="font-size:13px;font-weight:700;color:#fff;'
                    'margin:24px 0 12px;">Most-Changed Fields by Risk</div>',
                    unsafe_allow_html=True)

        sorted_fields = sorted(
            field_risk.items(),
            key=lambda x: sum(x[1]) / len(x[1]),
            reverse=True
        )[:10]

        max_avg = max((sum(v)/len(v)) for _, v in sorted_fields) or 1

        for field, scores in sorted_fields:
            avg = sum(scores) / len(scores)
            pct = int(avg / max_avg * 100)
            bar_col = "#ff5050" if avg >= 60 else "#fbbf24" if avg >= 30 else "#00ff88"
            label = field.replace("_", " ").title()
            st.markdown(
                f'<div style="margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">'
                f'<span>{label}</span>'
                f'<span style="color:{bar_col};font-weight:700;">'
                f'{avg:.0f} &nbsp;·&nbsp; {len(scores)} change{"s" if len(scores)>1 else ""}'
                f'</span></div>'
                f'<div class="stat-bar-wrap">'
                f'<div class="stat-bar-fill" style="width:{pct}%;background:{bar_col};"></div>'
                f'</div></div>',
                unsafe_allow_html=True
            )

    # ── Heatmap grid: template vs field ───────────────────────────────────
    # Build: {template_name: {field_key: avg_score}}
    tmpl_field: dict = defaultdict(lambda: defaultdict(list))
    for h in history:
        tmpl = h.get("template", "Unknown")[:25]
        for d in h.get("discrepancies", []):
            rs = {"HIGH": 80, "MEDIUM": 40, "LOW": 10}.get(d.get("risk_level","LOW"), 10)
            tmpl_field[tmpl][d.get("field_key","?")].append(rs)

    if tmpl_field:
        st.markdown('<div style="font-size:13px;font-weight:700;color:#fff;'
                    'margin:24px 0 8px;">Risk Heatmap — Template × Field</div>',
                    unsafe_allow_html=True)
        st.markdown("""<div class="hm-legend">
            <span>Low</span>
            <div class="hm-legend-grad"></div>
            <span>High</span>
        </div>""", unsafe_allow_html=True)

        # Collect all unique fields
        all_fields = sorted({
            fk for fields in tmpl_field.values() for fk in fields
        })[:8]  # cap at 8 for readability

        templates_list = list(tmpl_field.keys())
        ncols = len(all_fields) + 1  # +1 for row label

        # Header row
        header_cells = '<div class="hm-header">Template</div>' + "".join(
            f'<div class="hm-header">{f.replace("_"," ").replace("amount","amt").title()}</div>'
            for f in all_fields
        )
        st.markdown(
            f'<div class="hm-grid" style="grid-template-columns: 160px {" ".join(["1fr"]*len(all_fields))};">'
            f'{header_cells}',
            unsafe_allow_html=True
        )

        # Data rows
        for tmpl in templates_list:
            row_label = f'<div class="hm-row-label">{tmpl}</div>'
            cells = ""
            for fk in all_fields:
                scores_list = tmpl_field[tmpl].get(fk, [])
                if scores_list:
                    avg = sum(scores_list) / len(scores_list)
                    bg  = _score_to_color(avg)
                    tc  = _text_color(avg)
                    cells += (f'<div class="hm-cell" style="background:{bg};color:{tc};" '
                              f'title="{fk}: {avg:.0f}">{avg:.0f}</div>')
                else:
                    cells += '<div class="hm-cell" style="background:rgba(255,255,255,0.04);color:rgba(255,255,255,0.15);">—</div>'
            st.markdown(row_label + cells, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Recent comparisons ─────────────────────────────────────────────────
    st.markdown('<div style="font-size:13px;font-weight:700;color:#fff;'
                'margin:24px 0 12px;">Recent Comparisons</div>',
                unsafe_allow_html=True)

    rows = ""
    for h in reversed(history[-10:]):
        sc   = h["score"]
        col  = "#ff5050" if sc >= 50 else "#fbbf24" if sc >= 20 else "#00ff88"
        ts   = time.strftime("%H:%M:%S", time.localtime(h["timestamp"]))
        rows += (f'<tr>'
                 f'<td style="color:rgba(255,255,255,0.35);font-size:11px;">{ts}</td>'
                 f'<td style="color:#fff;font-size:12px;">{h["template"][:30]}</td>'
                 f'<td style="color:rgba(255,255,255,0.5);font-size:12px;">{h["incoming"][:30]}</td>'
                 f'<td style="color:{col};font-weight:700;text-align:right;">{sc:.0f}</td>'
                 f'<td style="color:#ff5050;text-align:right;">{h["high"]}</td>'
                 f'</tr>')

    st.markdown(
        '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
        'border-radius:12px;overflow:hidden;">'
        '<table class="tmpl-table" style="font-size:12px;">'
        '<thead><tr><th>Time</th><th>Reference</th><th>Incoming</th>'
        '<th style="text-align:right;">Score</th><th style="text-align:right;">HIGH</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>',
        unsafe_allow_html=True
    )


def _render_demo_heatmap():
    """Show a demo heatmap with placeholder data to illustrate the feature."""
    st.markdown('<div style="font-size:12px;color:rgba(255,255,255,0.3);'
                'margin-bottom:12px;font-style:italic;">Demo view — run comparisons to replace with real data</div>',
                unsafe_allow_html=True)

    fields   = ["Notional", "Fixed Rate", "Maturity", "Governing Law", "ISDA Ver", "Currency"]
    tmpls    = ["IRS_Goldman_USD", "IRS_Citibank_GBP", "CDS_Barclays_EUR", "FX_JPMorgan_EUR"]
    demo_scores = [
        [85, 10, 20, 5,  70, 5 ],
        [10, 60, 10, 80, 10, 5 ],
        [30, 20, 75, 10, 5,  90],
        [5,  5,  10, 50, 20, 15],
    ]

    st.markdown("""<div class="hm-legend">
        <span style="font-size:10px;color:rgba(255,255,255,0.3);">Low</span>
        <div class="hm-legend-grad"></div>
        <span style="font-size:10px;color:rgba(255,255,255,0.3);">High</span>
    </div>""", unsafe_allow_html=True)

    header = '<div class="hm-header">Template</div>' + "".join(
        f'<div class="hm-header">{f}</div>' for f in fields
    )
    st.markdown(
        f'<div class="hm-grid" style="grid-template-columns: 150px {" ".join(["1fr"]*len(fields))};">'
        f'{header}',
        unsafe_allow_html=True
    )
    for tmpl, scores_row in zip(tmpls, demo_scores):
        row_label = f'<div class="hm-row-label">{tmpl}</div>'
        cells = "".join(
            f'<div class="hm-cell" style="background:{_score_to_color(s)};'
            f'color:{_text_color(s)};">{s}</div>'
            for s in scores_row
        )
        st.markdown(row_label + cells, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
