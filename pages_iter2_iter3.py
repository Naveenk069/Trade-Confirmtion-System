"""
pages_iter2_iter3.py — Streamlit UI pages for Iteration 2 & 3.

Import and call these from app.py:

    from pages_iter2_iter3 import page_diff, page_generate
    # then add to nav and routing in main()

"""

import streamlit as st
import requests
import json
import time

API_BASE = "http://localhost:8000"

# ── reuse helpers from app.py ─────────────────────────────────────────────

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

def _risk_color(level):
    return {"HIGH": "#ff5050", "MEDIUM": "#fbbf24", "LOW": "#00ff88"}.get(level, "#aaa")

def _change_icon(ct):
    return {"CHANGED":"⚡","MISSING":"❌","ADDED":"➕","NUMERIC_DRIFT":"📊","MATCH":"✅"}.get(ct,"•")

def _severity_color(s):
    return {"ERROR":"#ff5050","WARNING":"#fbbf24","INFO":"#00d4ff"}.get(s,"#aaa")


# ── shared CSS injected once ──────────────────────────────────────────────
ITER_CSS = """
<style>
/* ── Risk badge ── */
.risk-badge {
    display:inline-block; padding:2px 10px; border-radius:20px;
    font-size:11px; font-weight:700; letter-spacing:.5px;
    font-family:'Syne',sans-serif;
}
.rb-HIGH   { background:rgba(255,80,80,.15);   color:#ff5050; border:1px solid rgba(255,80,80,.3); }
.rb-MEDIUM { background:rgba(251,191,36,.15);  color:#fbbf24; border:1px solid rgba(251,191,36,.3);}
.rb-LOW    { background:rgba(0,255,136,.15);   color:#00ff88; border:1px solid rgba(0,255,136,.3); }
/* ── Discrepancy card ── */
.disc-card {
    background:rgba(255,255,255,.03); border-radius:12px;
    border:1px solid rgba(255,255,255,.08); padding:18px 20px;
    margin-bottom:12px; transition:border-color .2s;
}
.disc-card:hover { border-color:rgba(0,212,255,.25); }
.disc-field   { font-family:'Syne',sans-serif; font-size:15px; font-weight:700; color:#fff; }
.disc-cat     { font-size:11px; color:rgba(255,255,255,.35); margin-left:8px; }
.disc-values  { display:flex; gap:24px; margin:10px 0; flex-wrap:wrap; }
.disc-val-box { background:rgba(255,255,255,.04); border-radius:8px;
                padding:8px 14px; flex:1; min-width:180px; }
.disc-val-label { font-size:10px; color:rgba(255,255,255,.3);
                  text-transform:uppercase; letter-spacing:1px; margin-bottom:3px; }
.disc-val-text  { font-size:13px; color:#fff; font-weight:500; }
.disc-explain   { font-size:12px; color:rgba(255,255,255,.4);
                  border-left:2px solid rgba(0,212,255,.2); padding-left:10px; margin-top:8px; }
/* ── Score ring ── */
.score-ring-wrap { text-align:center; padding:20px; }
.score-number    { font-family:'Syne',sans-serif; font-size:52px; font-weight:800; }
.score-label     { font-size:12px; color:rgba(255,255,255,.4);
                   text-transform:uppercase; letter-spacing:1.5px; }
/* ── Validation issue ── */
.vld-row { display:flex; gap:10px; align-items:flex-start;
           padding:10px 14px; border-radius:10px; margin-bottom:8px; }
.vld-ERROR   { background:rgba(255,80,80,.08);   border:1px solid rgba(255,80,80,.2); }
.vld-WARNING { background:rgba(251,191,36,.08);  border:1px solid rgba(251,191,36,.2);}
.vld-INFO    { background:rgba(0,212,255,.08);   border:1px solid rgba(0,212,255,.2); }
.vld-icon    { font-size:16px; margin-top:1px; }
.vld-text    { font-size:13px; }
.vld-rule    { font-size:10px; color:rgba(255,255,255,.3); margin-top:2px; }
/* ── Populated preview ── */
.populated-preview {
    background:rgba(255,255,255,.03); border:1px solid rgba(0,212,255,.15);
    border-radius:12px; padding:20px 24px; font-family:'DM Mono',monospace;
    font-size:12px; color:rgba(255,255,255,.65); line-height:1.8;
    max-height:400px; overflow-y:auto; white-space:pre-wrap;
}
</style>
"""


# ══════════════════════════════════════════════════════════════════════════
#  PAGE: DIFF ENGINE  (Iteration 2)
# ══════════════════════════════════════════════════════════════════════════

def page_diff():
    st.markdown(ITER_CSS, unsafe_allow_html=True)
    st.markdown("""<div class="page-header">
    <div class="page-title">Difference <span>Highlighter</span></div>
    <div class="page-subtitle">Compare two trade confirmations — all critical fields highlighted by risk level</div>
</div>""", unsafe_allow_html=True)

    # ── Mode selector ────────────────────────────────────────────────
    mode = st.radio(
        "Comparison mode",
        ["Compare stored templates", "Upload two .docx files", "Paste text directly"],
        horizontal=True,
        label_visibility="collapsed",
    )

    compare_result = None

    # ── Mode A: stored templates ─────────────────────────────────────
    if mode == "Compare stored templates":
        data = _api_get("/templates?active_only=false")
        templates = data.get("templates", []) if data else []
        if not templates:
            st.markdown('<div class="alert alert-error">❌ No templates in store. Ingest templates first.</div>',
                        unsafe_allow_html=True)
            return

        options = {f"{t['filename']}  [{t['trade_type']}]": t["doc_id"] for t in templates}
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div style="font-size:12px;color:rgba(255,255,255,.4);margin-bottom:4px;">📄 REFERENCE TEMPLATE</div>',
                        unsafe_allow_html=True)
            tmpl_sel = st.selectbox("Reference", list(options.keys()), key="d_tmpl",
                                    label_visibility="collapsed")
        with col2:
            st.markdown('<div style="font-size:12px;color:rgba(255,255,255,.4);margin-bottom:4px;">📄 INCOMING DOCUMENT</div>',
                        unsafe_allow_html=True)
            inc_sel  = st.selectbox("Incoming",  list(options.keys()), key="d_inc",
                                    label_visibility="collapsed")

        if st.button("⚡  Compare", use_container_width=False, key="btn_cmp_stored"):
            with st.spinner("Extracting fields and computing diff…"):
                compare_result = _api_post("/diff/compare", {
                    "template_doc_id": options[tmpl_sel],
                    "incoming_doc_id": options[inc_sel],
                })

    # ── Mode B: upload files ─────────────────────────────────────────
    elif mode == "Upload two .docx files":
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div style="font-size:12px;color:rgba(255,255,255,.4);margin-bottom:4px;">📄 REFERENCE TEMPLATE</div>',
                        unsafe_allow_html=True)
            tmpl_file = st.file_uploader("Template", type=["docx","txt"],
                                         key="d_up_tmpl", label_visibility="collapsed")
        with col2:
            st.markdown('<div style="font-size:12px;color:rgba(255,255,255,.4);margin-bottom:4px;">📄 INCOMING DOCUMENT</div>',
                        unsafe_allow_html=True)
            inc_file  = st.file_uploader("Incoming", type=["docx","txt"],
                                         key="d_up_inc", label_visibility="collapsed")

        if tmpl_file and inc_file:
            if st.button("⚡  Compare", key="btn_cmp_upload"):
                with st.spinner("Uploading and comparing…"):
                    try:
                        r = requests.post(
                            f"{API_BASE}/diff/compare-upload",
                            files={
                                "template_file": (tmpl_file.name, tmpl_file.getvalue(),
                                    "application/octet-stream"),
                                "incoming_file":  (inc_file.name,  inc_file.getvalue(),
                                    "application/octet-stream"),
                            }, timeout=30)
                        compare_result = r.json()
                    except Exception as e:
                        compare_result = {"error": str(e)}

    # ── Mode C: paste text ───────────────────────────────────────────
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div style="font-size:12px;color:rgba(255,255,255,.4);margin-bottom:4px;">📄 REFERENCE TEMPLATE</div>',
                        unsafe_allow_html=True)
            tmpl_txt = st.text_area("Paste template text", height=200,
                                    placeholder="Paste or type reference template text…",
                                    key="d_txt_tmpl", label_visibility="collapsed")
        with col2:
            st.markdown('<div style="font-size:12px;color:rgba(255,255,255,.4);margin-bottom:4px;">📄 INCOMING DOCUMENT</div>',
                        unsafe_allow_html=True)
            inc_txt  = st.text_area("Paste incoming text", height=200,
                                    placeholder="Paste or type incoming document text…",
                                    key="d_txt_inc", label_visibility="collapsed")

        if tmpl_txt and inc_txt:
            if st.button("⚡  Compare", key="btn_cmp_text"):
                with st.spinner("Analysing differences…"):
                    compare_result = _api_post("/diff/compare-text", {
                        "template_text": tmpl_txt,
                        "incoming_text": inc_txt,
                        "template_name": "Reference",
                        "incoming_name": "Incoming",
                    })

    # ── Render diff result ───────────────────────────────────────────
    if compare_result:
        if "error" in compare_result:
            st.markdown(f'<div class="alert alert-error">❌ {compare_result["error"]}</div>',
                        unsafe_allow_html=True)
            return
        _render_diff_report(compare_result)


def _render_diff_report(r: dict):
    """Render a DiffReport dict as a rich Streamlit UI."""
    total = r.get("total_discrepancies", 0)
    high  = r.get("high_risk_count", 0)
    med   = r.get("medium_risk_count", 0)
    low   = r.get("low_risk_count", 0)
    matches = len(r.get("matches", []))
    score = r.get("risk_score", 0)
    needs_review = r.get("needs_review", False)

    # Score + summary metrics
    score_color = "#ff5050" if score >= 50 else "#fbbf24" if score >= 20 else "#00ff88"
    review_html = (
        '<span style="color:#ff5050;font-weight:700;">⚠ REVIEW REQUIRED</span>'
        if needs_review else
        '<span style="color:#00ff88;font-weight:700;">✅ NO CRITICAL ISSUES</span>'
    )

    st.markdown(f"""<div style="background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.08);
            border-radius:16px; padding:24px; margin:20px 0;">
    <div style="display:flex; gap:32px; align-items:center; flex-wrap:wrap;">
        <div class="score-ring-wrap" style="min-width:120px;">
            <div class="score-number" style="color:{score_color};">{score:.0f}</div>
            <div class="score-label">Risk Score / 100</div>
        </div>
        <div style="flex:1;">
            <div style="font-family:'Syne',sans-serif; font-size:18px; font-weight:700;
                        color:#fff; margin-bottom:12px;">{review_html}</div>
            <div style="display:flex; gap:16px; flex-wrap:wrap;">
                <div style="text-align:center;">
                    <div style="font-family:'Syne',sans-serif; font-size:28px;
                                font-weight:800; color:#ff5050;">{high}</div>
                    <div style="font-size:11px; color:rgba(255,255,255,.35);">HIGH RISK</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-family:'Syne',sans-serif; font-size:28px;
                                font-weight:800; color:#fbbf24;">{med}</div>
                    <div style="font-size:11px; color:rgba(255,255,255,.35);">MEDIUM</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-family:'Syne',sans-serif; font-size:28px;
                                font-weight:800; color:#00ff88;">{low}</div>
                    <div style="font-size:11px; color:rgba(255,255,255,.35);">LOW</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-family:'Syne',sans-serif; font-size:28px;
                                font-weight:800; color:rgba(255,255,255,.3);">{matches}</div>
                    <div style="font-size:11px; color:rgba(255,255,255,.3);">MATCH</div>
                </div>
            </div>
        </div>
        <div style="font-size:12px; color:rgba(255,255,255,.25); text-align:right;">
            <div>{r.get('template_filename','')}</div>
            <div style="color:rgba(0,212,255,.5); margin:4px 0;">vs</div>
            <div>{r.get('incoming_filename','')}</div>
        </div>
    </div>
</div>""", unsafe_allow_html=True)

    if not r.get("discrepancies"):
        st.markdown('<div class="alert alert-success">✅ All fields are identical — no discrepancies found.</div>',
                    unsafe_allow_html=True)
        return

    # Filter controls
    st.markdown('<div style="font-family:\'Syne\',sans-serif; font-size:12px; font-weight:700; color:rgba(255,255,255,.4); text-transform:uppercase; letter-spacing:1.5px; margin:20px 0 10px;">Filter Discrepancies</div>',
                unsafe_allow_html=True)

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        risk_filter = st.multiselect("Risk Level", ["HIGH","MEDIUM","LOW"],
                                     default=["HIGH","MEDIUM","LOW"], key="df_risk")
    with fc2:
        cat_filter  = st.multiselect("Category",
                                     ["economic","legal","counterparty","identity"],
                                     default=["economic","legal","counterparty","identity"],
                                     key="df_cat")
    with fc3:
        change_filter = st.multiselect("Change Type",
                                       ["CHANGED","MISSING","ADDED","NUMERIC_DRIFT"],
                                       default=["CHANGED","MISSING","ADDED","NUMERIC_DRIFT"],
                                       key="df_change")

    filtered = [
        d for d in r["discrepancies"]
        if d["risk_level"]  in risk_filter
        and d["category"]   in cat_filter
        and d["change_type"] in change_filter
    ]

    st.markdown(f'<div style="font-size:12px; color:rgba(255,255,255,.3); margin:8px 0 16px;">'
                f'Showing {len(filtered)} of {total} discrepancies</div>', unsafe_allow_html=True)

    for d in filtered:
        rc    = _risk_color(d["risk_level"])
        ci    = _change_icon(d["change_type"])
        delta_html = ""
        if d.get("numeric_pct") is not None:
            sign = "+" if d["numeric_pct"] >= 0 else ""
            delta_html = f'<span style="color:#fbbf24; font-size:12px; margin-left:8px;">Δ {sign}{d["numeric_pct"]:.2f}%</span>'
        sim_html = ""
        if d.get("similarity") is not None:
            sim_html = f'<span style="font-size:11px; color:rgba(255,255,255,.3); margin-left:8px;">similarity {d["similarity"]:.0%}</span>'

        st.markdown(f"""<div class="disc-card">
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
        <span class="risk-badge rb-{d['risk_level']}">{d['risk_level']}</span>
        <span style="font-size:16px;">{ci}</span>
        <span class="disc-field">{d['field_name']}</span>
        <span class="disc-cat">{d['category']}</span>
        {delta_html}{sim_html}
    </div>
    <div class="disc-values">
        <div class="disc-val-box">
            <div class="disc-val-label">📄 Template</div>
            <div class="disc-val-text">{d['template_value'] or '<em style="opacity:.4">empty</em>'}</div>
        </div>
        <div class="disc-val-box" style="border:1px solid rgba(255,80,80,.15);">
            <div class="disc-val-label" style="color:#ff5050;">📥 Incoming</div>
            <div class="disc-val-text">{d['incoming_value'] or '<em style="opacity:.4">empty</em>'}</div>
        </div>
    </div>
    {f'<div class="disc-explain">→ {d["explanation"]}</div>' if d.get("explanation") else ""}
</div>""", unsafe_allow_html=True)

    # Matching fields (collapsed)
    if r.get("matches"):
        with st.expander(f"✅ View {len(r['matches'])} matching fields"):
            rows = "".join(
                f'<tr><td style="padding:6px 12px;color:#fff;font-weight:600;">{m["field_key"]}</td>'
                f'<td style="padding:6px 12px;color:rgba(255,255,255,.5);">{m["value"]}</td></tr>'
                for m in r["matches"]
            )
            st.markdown(f'<table style="width:100%;border-collapse:collapse;">{rows}</table>',
                        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE: TEMPLATE GENERATOR  (Iteration 3)
# ══════════════════════════════════════════════════════════════════════════

def page_generate():
    st.markdown(ITER_CSS, unsafe_allow_html=True)
    st.markdown("""<div class="page-header">
    <div class="page-title">Template <span>Generator</span></div>
    <div class="page-subtitle">Auto-fill, AI clause suggestions & rule-based validation — three stages, one click</div>
</div>""", unsafe_allow_html=True)

    # ── Input method ─────────────────────────────────────────────────
    input_mode = st.radio(
        "Input method",
        ["Form input", "Paste JSON", "Upload JSON file", "Upload CSV file"],
        horizontal=True,
        label_visibility="collapsed",
    )

    trade_data = None
    template_filename = None

    # ── Form input ───────────────────────────────────────────────────
    if input_mode == "Form input":
        st.markdown('<div style="background:rgba(255,255,255,.02); border:1px solid rgba(255,255,255,.07); border-radius:14px; padding:22px; margin-bottom:16px;">',
                    unsafe_allow_html=True)
        st.markdown('<div class="filter-title">⚡ Trade Identity</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: tt  = st.selectbox("Trade Type", ["Interest Rate Swap","FX Forward","Credit Default Swap","Equity Swap",""], key="g_tt")
        with c2: cp  = st.text_input("Counterparty", placeholder="Goldman Sachs", key="g_cp")
        with c3: cur = st.selectbox("Currency", ["USD","GBP","EUR","JPY","CHF",""], key="g_cur")
        with c4: jur = st.selectbox("Jurisdiction", ["US","UK","EU","APAC",""], key="g_jur")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div style="background:rgba(255,255,255,.02); border:1px solid rgba(255,255,255,.07); border-radius:14px; padding:22px; margin-bottom:16px;">',
                    unsafe_allow_html=True)
        st.markdown('<div class="filter-title">💰 Economic Terms</div>', unsafe_allow_html=True)
        e1, e2, e3 = st.columns(3)
        with e1: notional  = st.text_input("Notional Amount", placeholder="USD 50,000,000", key="g_not")
        with e2: fixed_r   = st.text_input("Fixed Rate",      placeholder="4.25% per annum", key="g_fr")
        with e3: pay_freq  = st.selectbox("Payment Frequency", ["Quarterly","Semi-Annual","Annual","Monthly","At Maturity",""], key="g_pf")
        d1, d2 = st.columns(2)
        with d1: eff_date  = st.text_input("Effective Date",  placeholder="April 1, 2026", key="g_ed")
        with d2: mat_date  = st.text_input("Maturity Date",   placeholder="April 1, 2031", key="g_md")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div style="background:rgba(255,255,255,.02); border:1px solid rgba(255,255,255,.07); border-radius:14px; padding:22px; margin-bottom:16px;">',
                    unsafe_allow_html=True)
        st.markdown('<div class="filter-title">🏛 Parties</div>', unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        with p1: party_a = st.text_input("Party A (full legal name)", key="g_pa")
        with p2: party_b = st.text_input("Party B (full legal name)", key="g_pb")
        st.markdown('</div>', unsafe_allow_html=True)

        # Optional overrides
        with st.expander("⚙ Override auto-suggested fields"):
            o1, o2, o3 = st.columns(3)
            with o1: gov_law = st.text_input("Governing Law", placeholder="Auto-suggested", key="g_gl")
            with o2: isda    = st.text_input("ISDA Version",  placeholder="Auto-suggested", key="g_isda")
            with o3: dc      = st.text_input("Day Count",     placeholder="Auto-suggested", key="g_dc")
            template_filename = st.text_input("Base Template Filename (optional)",
                                              placeholder="e.g. IRS_GoldmanSachs_USD_v1.docx", key="g_tmpl")

        trade_data = {k: v for k, v in {
            "trade_type": tt, "counterparty": cp, "currency": cur,
            "jurisdiction": jur, "notional_amount": notional,
            "fixed_rate": fixed_r, "payment_frequency": pay_freq,
            "effective_date": eff_date, "maturity_date": mat_date,
            "party_a": party_a, "party_b": party_b,
            "governing_law": gov_law, "isda_version": isda, "day_count": dc,
        }.items() if v}
        if template_filename:
            trade_data["template_filename"] = template_filename

    # ── Paste JSON ───────────────────────────────────────────────────
    elif input_mode == "Paste JSON":
        sample_r = requests.get(f"{API_BASE}/generate/sample-input", timeout=3)
        sample   = json.dumps(sample_r.json(), indent=2) if sample_r.status_code == 200 else "{}"
        raw = st.text_area("Trade data JSON", value=sample, height=300, key="g_json")
        try:
            trade_data = json.loads(raw)
            trade_data.pop("_notes", None)
        except Exception:
            st.markdown('<div class="alert alert-error">❌ Invalid JSON — check syntax.</div>',
                        unsafe_allow_html=True)

    # ── Upload JSON ──────────────────────────────────────────────────
    elif input_mode == "Upload JSON file":
        up_json = st.file_uploader("Upload JSON", type=["json"], key="g_ujson",
                                   label_visibility="collapsed")
        if up_json:
            try:
                trade_data = json.loads(up_json.read())
                trade_data.pop("_notes", None)
                st.markdown(f'<div class="alert alert-info">📎 {up_json.name} loaded — {len(trade_data)} fields</div>',
                            unsafe_allow_html=True)
            except Exception:
                st.markdown('<div class="alert alert-error">❌ Could not parse JSON file.</div>',
                            unsafe_allow_html=True)

    # ── Upload CSV ───────────────────────────────────────────────────
    elif input_mode == "Upload CSV file":
        up_csv = st.file_uploader("Upload CSV", type=["csv"], key="g_ucsv",
                                  label_visibility="collapsed")
        row_idx = st.number_input("Row index (0 = first data row)", min_value=0, value=0, key="g_row")
        if up_csv:
            import csv, io
            reader = csv.DictReader(io.StringIO(up_csv.read().decode()))
            rows   = list(reader)
            if rows and row_idx < len(rows):
                trade_data = dict(rows[row_idx])
                st.markdown(f'<div class="alert alert-info">📎 Row {row_idx}: {len(trade_data)} fields loaded</div>',
                            unsafe_allow_html=True)

    # ── Generate button ───────────────────────────────────────────────
    if trade_data:
        if st.button("🚀  Generate Template", use_container_width=False, key="btn_gen"):
            payload = {k: v for k, v in trade_data.items() if v and k != "template_filename"}
            if template_filename:
                payload["template_filename"] = template_filename

            with st.spinner("Running 3-stage pipeline: auto-fill → AI clauses → validation…"):
                result = _api_post("/generate", payload)

            if not result or "error" in result:
                st.markdown(f'<div class="alert alert-error">❌ Generation failed: {result.get("error","") if result else "API unreachable"}</div>',
                            unsafe_allow_html=True)
                return

            _render_generate_result(result)


def _render_generate_result(r: dict):
    """Render a generation result with pipeline stats, validation, and preview."""
    score     = r.get("validation_score", 0)
    is_valid  = r.get("is_valid", False)
    issues    = r.get("validation_issues", [])
    errors    = [i for i in issues if i["severity"] == "ERROR"]
    warnings  = [i for i in issues if i["severity"] == "WARNING"]
    infos     = [i for i in issues if i["severity"] == "INFO"]

    score_color = "#00ff88" if score >= 70 else "#fbbf24" if score >= 40 else "#ff5050"

    # Pipeline stats banner
    st.markdown(f"""<div style="background:rgba(0,212,255,.05); border:1px solid rgba(0,212,255,.15);
            border-radius:14px; padding:22px; margin:20px 0;">
    <div style="display:flex; gap:32px; align-items:center; flex-wrap:wrap;">
        <div class="score-ring-wrap">
            <div class="score-number" style="color:{score_color};">{score:.0f}</div>
            <div class="score-label">Validation Score</div>
        </div>
        <div style="display:flex; gap:24px; flex-wrap:wrap; flex:1;">
            <div>
                <div style="font-family:'Syne',sans-serif; font-size:26px; font-weight:800; color:#00d4ff;">
                    {r.get('autofill_count',0)}
                </div>
                <div style="font-size:11px; color:rgba(255,255,255,.35);">FIELDS AUTO-FILLED</div>
            </div>
            <div>
                <div style="font-family:'Syne',sans-serif; font-size:26px; font-weight:800; color:#a855f7;">
                    {r.get('ai_clause_count',0)}
                </div>
                <div style="font-size:11px; color:rgba(255,255,255,.35);">AI CLAUSES SUGGESTED</div>
            </div>
            <div>
                <div style="font-family:'Syne',sans-serif; font-size:26px; font-weight:800; color:#{'00ff88' if len(errors)==0 else 'ff5050'};">
                    {len(errors)}
                </div>
                <div style="font-size:11px; color:rgba(255,255,255,.35);">ERRORS</div>
            </div>
            <div>
                <div style="font-family:'Syne',sans-serif; font-size:26px; font-weight:800; color:#fbbf24;">
                    {len(warnings)}
                </div>
                <div style="font-size:11px; color:rgba(255,255,255,.35);">WARNINGS</div>
            </div>
        </div>
        <div>
            {'<span style="color:#00ff88;font-weight:700;font-family:Syne,sans-serif;">✅ READY FOR REVIEW</span>'
             if is_valid else
             '<span style="color:#ff5050;font-weight:700;font-family:Syne,sans-serif;">❌ FIX ERRORS FIRST</span>'}
        </div>
    </div>
</div>""", unsafe_allow_html=True)

    # Auto-filled trade data
    trade_data = r.get("trade_data", {})
    if trade_data:
        with st.expander("📋 View all auto-filled field values"):
            important = ["trade_type","counterparty","currency","jurisdiction",
                         "notional_amount","fixed_rate","floating_rate","payment_frequency",
                         "effective_date","maturity_date","day_count",
                         "governing_law","isda_version","clearing_venue"]
            rows = ""
            for key in important:
                val = trade_data.get(key, "")
                if val:
                    is_suggested = key not in ["trade_type","counterparty","currency",
                                               "notional_amount","fixed_rate","effective_date","maturity_date"]
                    badge = '<span style="font-size:10px;color:#a855f7;margin-left:6px;">AI</span>' if is_suggested else ""
                    rows += f'<tr><td style="padding:6px 12px;color:rgba(255,255,255,.5);font-size:12px;">{key}</td><td style="padding:6px 12px;color:#fff;font-size:13px;">{val}{badge}</td></tr>'
            st.markdown(f'<table style="width:100%;border-collapse:collapse;">{rows}</table>',
                        unsafe_allow_html=True)

    # Validation issues
    if issues:
        st.markdown('<div style="font-family:\'Syne\',sans-serif; font-size:13px; font-weight:700; color:rgba(255,255,255,.4); text-transform:uppercase; letter-spacing:1px; margin:16px 0 10px;">Validation Issues</div>',
                    unsafe_allow_html=True)
        icons = {"ERROR":"❌","WARNING":"⚠️","INFO":"ℹ️"}
        for issue in issues:
            sc = _severity_color(issue["severity"])
            st.markdown(f"""<div class="vld-row vld-{issue['severity']}">
    <div class="vld-icon">{icons.get(issue['severity'],'•')}</div>
    <div>
        <div class="vld-text" style="color:{sc};">
            <b>{issue['field']}</b>: {issue['message']}
        </div>
        <div class="vld-rule">{issue['rule_id']}</div>
    </div>
</div>""", unsafe_allow_html=True)

    # Document preview
    st.markdown('<div style="font-family:\'Syne\',sans-serif; font-size:13px; font-weight:700; color:rgba(255,255,255,.4); text-transform:uppercase; letter-spacing:1px; margin:20px 0 10px;">Document Preview</div>',
                unsafe_allow_html=True)
    preview_text = r.get("populated_text", "")
    st.markdown(f'<div class="populated-preview">{preview_text}</div>',
                unsafe_allow_html=True)

    # Download
    download_url = r.get("download_url", "")
    filename     = r.get("filename", "populated_template.docx")
    if download_url:
        st.markdown(f"""<div style="margin-top:20px;">
    <a href="{API_BASE}{download_url}" target="_blank"
       style="display:inline-flex; align-items:center; gap:8px;
              padding:10px 22px; border-radius:10px;
              background:linear-gradient(135deg,#00d4ff,#00a8cc);
              color:#000; font-weight:700; font-size:13px;
              text-decoration:none; font-family:'Syne',sans-serif;">
        ⬇ Download {filename}
    </a>
</div>""", unsafe_allow_html=True)
