"""
page_sidebyside.py — Side-by-Side Document Viewer (P2 Feature).

Renders two documents side by side with:
- Changed fields highlighted red/green inline
- Colour-coded diff markers per line
- Synced scrolling feel via HTML layout
- Risk badges on each changed line
"""

import streamlit as st
import requests
import html as _html

API_BASE = "http://localhost:8000"

SBS_CSS = """
<style>
.sbs-wrap {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 16px;
}
.sbs-panel {
    background: #0D1B35;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    overflow: hidden;
}
.sbs-header {
    padding: 12px 18px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.sbs-body {
    padding: 18px;
    font-family: 'DM Mono', 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.8;
    max-height: 520px;
    overflow-y: auto;
}
.sbs-line { padding: 2px 8px; border-radius: 4px; margin: 1px 0; }
.sbs-line-match   { color: rgba(255,255,255,0.6); }
.sbs-line-changed { background: rgba(245,158,11,0.1); color: #fbbf24;
                    border-left: 3px solid #fbbf24; padding-left: 10px; }
.sbs-line-added   { background: rgba(0,255,136,0.08); color: #00ff88;
                    border-left: 3px solid #00ff88; padding-left: 10px; }
.sbs-line-removed { background: rgba(255,80,80,0.08); color: #ff5050;
                    border-left: 3px solid #ff5050; padding-left: 10px; }
.sbs-line-key     { color: rgba(0,212,255,0.7); font-weight: 600; }
.diff-legend {
    display: flex; gap: 20px; flex-wrap: wrap;
    padding: 10px 0 16px;
    font-size: 11px;
}
.diff-legend-item { display: flex; align-items: center; gap: 6px; }
.legend-dot { width: 10px; height: 10px; border-radius: 2px; }
</style>
"""

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

def _build_field_map(diff_result: dict) -> dict:
    """Build field_key → {template_val, incoming_val, change_type, risk} from diff."""
    field_map = {}
    for d in diff_result.get("discrepancies", []):
        field_map[d["field_key"]] = {
            "tmpl":    d.get("template_value", ""),
            "inc":     d.get("incoming_value", ""),
            "change":  d.get("change_type", "CHANGED"),
            "risk":    d.get("risk_level", "LOW"),
        }
    for m in diff_result.get("matches", []):
        field_map[m["field_key"]] = {
            "tmpl":   m.get("value", ""),
            "inc":    m.get("value", ""),
            "change": "MATCH",
            "risk":   "LOW",
        }
    return field_map

def _line_class(change_type: str, side: str) -> str:
    if change_type == "MATCH":
        return "sbs-line sbs-line-match"
    if change_type == "MISSING":
        return "sbs-line sbs-line-removed" if side == "inc" else "sbs-line sbs-line-match"
    if change_type == "ADDED":
        return "sbs-line sbs-line-added" if side == "inc" else "sbs-line sbs-line-removed"
    return "sbs-line sbs-line-changed"

def _risk_badge(risk: str, change: str) -> str:
    if change == "MATCH":
        return ""
    colors = {"HIGH": "#ff5050", "MEDIUM": "#fbbf24", "LOW": "#00ff88"}
    c = colors.get(risk, "#aaa")
    return (f'<span style="display:inline-block;padding:0 6px;border-radius:10px;'
            f'font-size:9px;font-weight:700;margin-left:6px;'
            f'background:rgba({_hex_rgb(c)},0.15);color:{c};">{risk}</span>')

def _hex_rgb(h: str) -> str:
    h = h.lstrip("#")
    return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"

def _render_panel(title: str, color: str, field_map: dict, side: str) -> str:
    rows = ""
    for key, info in field_map.items():
        val = info["tmpl"] if side == "tmpl" else info["inc"]
        cls = _line_class(info["change"], side)
        badge = _risk_badge(info["risk"], info["change"])
        safe_key = _html.escape(key.replace("_", " ").title())
        safe_val = _html.escape(str(val)) if val else '<em style="opacity:0.3">—</em>'
        rows += (f'<div class="{cls}">'
                 f'<span class="sbs-line-key">{safe_key}:</span> '
                 f'{safe_val}{badge}</div>')

    return f"""
    <div class="sbs-panel">
        <div class="sbs-header" style="color:{color};">{title}</div>
        <div class="sbs-body">{rows}</div>
    </div>"""


def page_sidebyside():
    st.markdown(SBS_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="page-header">'
        '<div class="page-title">Side-by-Side <span>Diff Viewer</span></div>'
        '<div class="page-subtitle">Two documents side by side — every changed field highlighted inline by risk level</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Legend
    st.markdown("""<div class="diff-legend">
        <div class="diff-legend-item">
            <div class="legend-dot" style="background:#00ff88;"></div>
            <span style="color:rgba(255,255,255,0.5);">Added / New</span>
        </div>
        <div class="diff-legend-item">
            <div class="legend-dot" style="background:#fbbf24;"></div>
            <span style="color:rgba(255,255,255,0.5);">Changed</span>
        </div>
        <div class="diff-legend-item">
            <div class="legend-dot" style="background:#ff5050;"></div>
            <span style="color:rgba(255,255,255,0.5);">Removed / Missing</span>
        </div>
        <div class="diff-legend-item">
            <div class="legend-dot" style="background:rgba(255,255,255,0.15);"></div>
            <span style="color:rgba(255,255,255,0.5);">Matching</span>
        </div>
    </div>""", unsafe_allow_html=True)

    # Mode selector
    mode = st.radio("Source", ["Stored templates", "Upload files"],
                    horizontal=True, label_visibility="collapsed", key="sbs_mode")

    diff_result = None

    if mode == "Stored templates":
        data = _api_get("/templates?active_only=false")
        templates = data.get("templates", []) if data else []
        if not templates:
            st.markdown('<div class="alert alert-error">❌ No templates found.</div>',
                        unsafe_allow_html=True)
            return
        options = {f"{t['filename']}  [{t['trade_type']}]": t["doc_id"] for t in templates}
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div style="font-size:11px;color:rgba(0,212,255,0.6);'
                        'font-weight:700;margin-bottom:4px;">REFERENCE</div>',
                        unsafe_allow_html=True)
            sel_a = st.selectbox("Ref", list(options.keys()),
                                 key="sbs_a", label_visibility="collapsed")
        with c2:
            st.markdown('<div style="font-size:11px;color:rgba(255,80,80,0.6);'
                        'font-weight:700;margin-bottom:4px;">INCOMING</div>',
                        unsafe_allow_html=True)
            sel_b = st.selectbox("Inc", list(options.keys()),
                                 key="sbs_b", label_visibility="collapsed")
        if st.button("⚡  Compare Side by Side", key="sbs_btn", use_container_width=True):
            with st.spinner("Extracting and comparing fields…"):
                diff_result = _api_post("/diff/compare", {
                    "template_doc_id": options[sel_a],
                    "incoming_doc_id": options[sel_b],
                })

    else:
        c1, c2 = st.columns(2)
        with c1:
            f_a = st.file_uploader("Reference .docx", type=["docx","txt"], key="sbs_fa")
        with c2:
            f_b = st.file_uploader("Incoming .docx",  type=["docx","txt"], key="sbs_fb")
        if f_a and f_b and st.button("⚡  Compare Side by Side", key="sbs_btn2",
                                      use_container_width=True):
            import requests as _r
            with st.spinner("Comparing…"):
                resp = _r.post(
                    f"{API_BASE}/diff/compare-upload",
                    files={"template_file": (f_a.name, f_a.read()),
                           "incoming_file":  (f_b.name, f_b.read())},
                    timeout=20,
                )
                diff_result = resp.json() if resp.status_code == 200 else {"error": resp.text}

    if not diff_result:
        return

    if "error" in diff_result:
        st.markdown(f'<div class="alert alert-error">❌ {diff_result["error"]}</div>',
                    unsafe_allow_html=True)
        return

    # Summary bar
    score = diff_result.get("risk_score", 0)
    disc  = diff_result.get("total_discrepancies", 0)
    high  = diff_result.get("high_risk_count", 0)
    sc    = "#ff5050" if score >= 50 else "#fbbf24" if score >= 20 else "#00ff88"
    tmpl_name = diff_result.get("template_filename", "Reference")
    inc_name  = diff_result.get("incoming_filename", "Incoming")

    st.markdown(f"""<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;
        background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
        border-radius:12px;padding:14px 20px;margin:16px 0;">
        <div style="font-size:28px;font-weight:800;color:{sc};">{score:.0f}<span style="font-size:12px;color:rgba(255,255,255,0.3);"> /100</span></div>
        <div style="flex:1;">
            <div style="font-size:13px;font-weight:700;color:#fff;">{disc} discrepancies &nbsp;·&nbsp; {high} HIGH risk</div>
            <div style="font-size:11px;color:rgba(255,255,255,0.3);margin-top:3px;">
                {_html.escape(tmpl_name)} &nbsp;<span style="color:rgba(0,212,255,0.4);">vs</span>&nbsp; {_html.escape(inc_name)}
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Build side-by-side panels
    from src.auth import log_audit
    username = st.session_state.get("user", {}).get("username", "unknown")
    log_audit(username, "DIFF", f"Side-by-side: {tmpl_name} vs {inc_name}")

    field_map = _build_field_map(diff_result)
    if not field_map:
        st.markdown('<div class="alert alert-info">No field data to display.</div>',
                    unsafe_allow_html=True)
        return

    panel_a = _render_panel(f"📄 {tmpl_name}", "#00D4FF", field_map, "tmpl")
    panel_b = _render_panel(f"📥 {inc_name}", "#ff5050", field_map, "inc")

    st.markdown(
        f'<div class="sbs-wrap">{panel_a}{panel_b}</div>',
        unsafe_allow_html=True
    )
