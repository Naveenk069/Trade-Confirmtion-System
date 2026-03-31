"""
page_versions.py — Template Version Control (P2 Feature).

Shows all versions of each template grouped by base name.
Allows comparing any two versions via the diff engine.
Version history stored via the existing template metadata.
"""

import streamlit as st
import requests
from collections import defaultdict
import re
from src.auth import log_audit

API_BASE = "http://localhost:8000"


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


def _base_name(filename: str) -> str:
    """Strip version suffix: IRS_Goldman_v2.docx → IRS_Goldman"""
    name = re.sub(r"\.docx$", "", filename, flags=re.IGNORECASE)
    name = re.sub(r"_v\d+(\.\d+)?$", "", name)
    return name


def _version_badge(version: str, status: str) -> str:
    sc = {"active": "#00ff88", "draft": "#fbbf24", "deprecated": "#ff5050"}.get(status, "#aaa")
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:20px;'
            f'font-size:10px;font-weight:700;background:rgba(0,0,0,0.3);'
            f'border:1px solid {sc};color:{sc};">v{version}</span>')


def page_versions():
    st.markdown(
        '<div class="page-header">'
        '<div class="page-title">Version <span>Control</span></div>'
        '<div class="page-subtitle">All template versions grouped by document — compare any two versions side by side</div>'
        '</div>',
        unsafe_allow_html=True
    )

    username = st.session_state.get("user", {}).get("username", "unknown")

    # Load all templates including drafts and deprecated
    data = _api_get("/templates?active_only=false")
    if not data:
        st.markdown('<div class="alert alert-error">❌ Cannot reach API.</div>',
                    unsafe_allow_html=True)
        return

    templates = data.get("templates", [])
    if not templates:
        st.markdown('<div class="alert alert-info">No templates found. Upload templates first.</div>',
                    unsafe_allow_html=True)
        return

    # Group by base name
    groups: dict = defaultdict(list)
    for t in templates:
        base = _base_name(t["filename"])
        groups[base].append(t)

    # Sort each group by version
    for base in groups:
        groups[base].sort(key=lambda x: str(x.get("version", "1.0")))

    # ── Stats ──────────────────────────────────────────────────────────────
    multi_version = sum(1 for g in groups.values() if len(g) > 1)
    st.markdown(f"""<div class="metric-row">
        <div class="metric-card mc-cyan">
            <div class="metric-icon">📁</div>
            <div class="metric-value">{len(groups)}</div>
            <div class="metric-label">Document Families</div>
        </div>
        <div class="metric-card mc-green">
            <div class="metric-icon">📄</div>
            <div class="metric-value">{len(templates)}</div>
            <div class="metric-label">Total Versions</div>
        </div>
        <div class="metric-card mc-amber">
            <div class="metric-icon">🔀</div>
            <div class="metric-value">{multi_version}</div>
            <div class="metric-label">Multi-Version Docs</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Version groups ──────────────────────────────────────────────────────
    compare_result = None
    compare_names  = ("", "")

    for base, versions in sorted(groups.items()):
        has_multi = len(versions) > 1
        trade_type  = versions[-1].get("trade_type", "")
        counterparty = versions[-1].get("counterparty", "").split(" and ")[0][:30]

        # Group header
        status_colors = {"active":"#00ff88","draft":"#fbbf24","deprecated":"#ff5050"}
        latest_status = versions[-1].get("status","active")
        sc = status_colors.get(latest_status, "#aaa")

        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
            f'border-radius:14px;padding:18px 22px;margin-bottom:16px;">'
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">'
            f'<div style="font-size:14px;font-weight:700;color:#fff;">{base}</div>'
            f'<span style="font-size:11px;color:rgba(0,212,255,0.7);">{trade_type}</span>'
            f'<span style="font-size:11px;color:rgba(255,255,255,0.3);">{counterparty}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Version timeline
        ver_html = '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px;">'
        for i, t in enumerate(versions):
            is_latest = (i == len(versions) - 1)
            st_col = status_colors.get(t.get("status","active"), "#aaa")
            ver_html += (
                f'<div style="background:rgba(255,255,255,0.05);border:1px solid {st_col};'
                f'border-radius:10px;padding:8px 14px;min-width:120px;">'
                f'<div style="font-size:11px;font-weight:700;color:{st_col};">v{t.get("version","1.0")}'
                f'{" · LATEST" if is_latest else ""}</div>'
                f'<div style="font-size:10px;color:rgba(255,255,255,0.3);margin-top:2px;">'
                f'{t.get("filename","")}</div>'
                f'<div style="font-size:10px;color:rgba(255,255,255,0.2);margin-top:2px;">'
                f'{t.get("status","active").upper()}</div>'
                f'</div>'
            )
            if i < len(versions) - 1:
                ver_html += '<div style="color:rgba(255,255,255,0.2);font-size:18px;">→</div>'
        ver_html += '</div>'
        st.markdown(ver_html, unsafe_allow_html=True)

        # Compare two versions (only if >1 version exists)
        if has_multi:
            ver_options = {f"v{t['version']} — {t['filename']}": t["doc_id"] for t in versions}
            ver_keys = list(ver_options.keys())

            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                sel_a = st.selectbox("From version", ver_keys,
                                     index=0, key=f"vc_a_{base}")
            with c2:
                sel_b = st.selectbox("To version", ver_keys,
                                     index=len(ver_keys)-1, key=f"vc_b_{base}")
            with c3:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Compare", key=f"vc_btn_{base}", use_container_width=True):
                    with st.spinner("Comparing versions…"):
                        result = _api_post("/diff/compare", {
                            "template_doc_id": ver_options[sel_a],
                            "incoming_doc_id": ver_options[sel_b],
                        })
                    if result and "error" not in result:
                        compare_result = result
                        compare_names  = (sel_a, sel_b)
                        log_audit(username, "DIFF", f"Version compare: {sel_a} → {sel_b}")
                    else:
                        st.markdown(f'<div class="alert alert-error">❌ {result.get("error","")}</div>',
                                    unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="font-size:11px;color:rgba(255,255,255,0.2);font-style:italic;">'
                'Only one version — upload a v2 to enable version comparison</div>',
                unsafe_allow_html=True
            )

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Version diff result ────────────────────────────────────────────────
    if compare_result:
        st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="page-title" style="font-size:20px;margin-bottom:12px;">'
            f'Version <span>Diff</span></div>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div style="font-size:12px;color:rgba(255,255,255,0.4);margin-bottom:16px;">'
            f'{compare_names[0]} &nbsp;→&nbsp; {compare_names[1]}</div>',
            unsafe_allow_html=True
        )

        score = compare_result.get("risk_score", 0)
        disc  = compare_result.get("total_discrepancies", 0)
        sc    = "#ff5050" if score >= 50 else "#fbbf24" if score >= 20 else "#00ff88"

        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
            f'border-radius:12px;padding:14px 20px;margin-bottom:16px;">'
            f'<span style="font-size:24px;font-weight:800;color:{sc};">{score:.0f}</span>'
            f'<span style="font-size:11px;color:rgba(255,255,255,0.3);"> / 100 risk score &nbsp;·&nbsp; '
            f'{disc} field changes</span></div>',
            unsafe_allow_html=True
        )

        discs = compare_result.get("discrepancies", [])
        if not discs:
            st.markdown('<div class="alert alert-success">✅ No field changes between these versions.</div>',
                        unsafe_allow_html=True)
        else:
            rows = ""
            for d in discs:
                rc = {"HIGH":"#ff5050","MEDIUM":"#fbbf24","LOW":"#00ff88"}.get(d["risk_level"],"#aaa")
                rows += (
                    f'<tr>'
                    f'<td style="color:#fff;font-weight:600;">{d["field_key"].replace("_"," ").title()}</td>'
                    f'<td style="color:rgba(255,255,255,0.5);">{d.get("template_value","—")}</td>'
                    f'<td style="color:#00D4FF;">{d.get("incoming_value","—")}</td>'
                    f'<td><span style="color:{rc};font-weight:700;font-size:11px;">'
                    f'{d["risk_level"]}</span></td>'
                    f'<td style="color:rgba(255,255,255,0.4);font-size:11px;">{d.get("change_type","")}</td>'
                    f'</tr>'
                )
            st.markdown(
                '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
                'border-radius:12px;overflow:hidden;">'
                '<table class="tmpl-table" style="font-size:12px;">'
                '<thead><tr><th>Field</th><th>Previous</th><th>New</th>'
                '<th>Risk</th><th>Change</th></tr></thead>'
                f'<tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True
            )
