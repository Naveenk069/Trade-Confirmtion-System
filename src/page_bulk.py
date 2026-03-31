"""
page_bulk.py — Bulk Template Generation (P1 Feature).

Upload a CSV with multiple trade rows → generate one .docx per row →
return as a downloadable ZIP file.
"""

import streamlit as st
import requests
import json
import io
import csv
import zipfile
import time

API_BASE = "http://localhost:8000"


def _api_post_generate(payload: dict):
    try:
        r = requests.post(f"{API_BASE}/generate", json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _download_docx(filename: str) -> bytes | None:
    try:
        r = requests.get(f"{API_BASE}/generate/download/{filename}", timeout=15)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


SAMPLE_CSV = """trade_type,counterparty,notional_amount,currency,fixed_rate,effective_date,maturity_date,jurisdiction
Interest Rate Swap,Goldman Sachs,10000000,USD,3.5%,2026-04-01,2031-04-01,US
FX Forward,JP Morgan,5000000,EUR,N/A,2026-04-15,2026-10-15,UK
Credit Default Swap,Barclays,8000000,EUR,1.2%,2026-05-01,2031-05-01,EU
Equity Swap,Deutsche Bank,3000000,USD,2.8%,2026-06-01,2029-06-01,US
Interest Rate Swap,Citibank,15000000,GBP,3.1%,2026-04-01,2033-04-01,UK
"""


def page_bulk():
    st.markdown(
        '<div class="page-header">'
        '<div class="page-title">Bulk <span>Generation</span></div>'
        '<div class="page-subtitle">Upload a CSV with multiple trades — download all confirmations as a ZIP</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # ── How it works ──────────────────────────────────────────────────────
    st.markdown("""<div style="background:rgba(0,212,255,0.05);border:1px solid rgba(0,212,255,0.15);
        border-radius:12px;padding:18px 22px;margin-bottom:24px;">
        <div style="font-size:13px;font-weight:700;color:#00D4FF;margin-bottom:10px;">How it works</div>
        <div style="display:flex;gap:32px;flex-wrap:wrap;">
            <div style="font-size:12px;color:rgba(255,255,255,0.5);">
                <span style="color:#00FF88;font-weight:700;">1</span>&nbsp; Upload a CSV with one trade per row
            </div>
            <div style="font-size:12px;color:rgba(255,255,255,0.5);">
                <span style="color:#00FF88;font-weight:700;">2</span>&nbsp; System generates one .docx per row
            </div>
            <div style="font-size:12px;color:rgba(255,255,255,0.5);">
                <span style="color:#00FF88;font-weight:700;">3</span>&nbsp; All documents bundled into a ZIP
            </div>
            <div style="font-size:12px;color:rgba(255,255,255,0.5);">
                <span style="color:#00FF88;font-weight:700;">4</span>&nbsp; One-click download of all confirmations
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Sample CSV download ───────────────────────────────────────────────
    col1, col2 = st.columns([3, 1])
    with col2:
        st.download_button(
            "⬇ Download Sample CSV",
            data=SAMPLE_CSV,
            file_name="sample_trades.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ── File upload ───────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload Trade CSV",
        type=["csv"],
        help="CSV must have headers. Required: trade_type, counterparty, currency, jurisdiction"
    )

    if not uploaded:
        # Show sample structure
        st.markdown("""<div style="margin-top:16px;">
            <div style="font-size:11px;font-weight:700;color:rgba(255,255,255,0.3);
                letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;">
                Required CSV columns
            </div>""", unsafe_allow_html=True)

        cols_info = [
            ("trade_type", "Interest Rate Swap / FX Forward / Credit Default Swap / Equity Swap"),
            ("counterparty", "Counterparty name"),
            ("notional_amount", "e.g. 10000000"),
            ("currency", "USD / GBP / EUR / JPY / CHF"),
            ("fixed_rate", "e.g. 3.5%"),
            ("effective_date", "YYYY-MM-DD"),
            ("maturity_date", "YYYY-MM-DD"),
            ("jurisdiction", "US / UK / EU"),
        ]
        rows = "".join(
            f'<tr><td style="color:#00D4FF;font-weight:600;font-size:12px;">{c}</td>'
            f'<td style="color:rgba(255,255,255,0.45);font-size:11px;">{d}</td></tr>'
            for c, d in cols_info
        )
        st.markdown(
            '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
            'border-radius:12px;overflow:hidden;">'
            '<table class="tmpl-table" style="font-size:12px;">'
            f'<tbody>{rows}</tbody></table></div>',
            unsafe_allow_html=True
        )
        return

    # ── Parse CSV ─────────────────────────────────────────────────────────
    try:
        content = uploaded.read().decode("utf-8")
        reader  = list(csv.DictReader(io.StringIO(content)))
    except Exception as e:
        st.markdown(f'<div class="alert alert-error">❌ Could not parse CSV: {e}</div>',
                    unsafe_allow_html=True)
        return

    if not reader:
        st.markdown('<div class="alert alert-warn">⚠ CSV is empty.</div>', unsafe_allow_html=True)
        return

    st.markdown(
        f'<div class="alert alert-info">📋 Found <b>{len(reader)}</b> trade rows — ready to generate.</div>',
        unsafe_allow_html=True
    )

    # Preview table
    with st.expander(f"Preview CSV ({len(reader)} rows)"):
        headers = list(reader[0].keys())
        hdr_row = "".join(f"<th>{h}</th>" for h in headers)
        data_rows = ""
        for row in reader[:10]:
            data_rows += "<tr>" + "".join(
                f'<td style="color:rgba(255,255,255,0.7);font-size:11px;">{row.get(h,"")}</td>'
                for h in headers
            ) + "</tr>"
        if len(reader) > 10:
            data_rows += f'<tr><td colspan="{len(headers)}" style="color:rgba(255,255,255,0.3);font-size:11px;text-align:center;">... and {len(reader)-10} more rows</td></tr>'

        st.markdown(
            '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
            'border-radius:12px;overflow:hidden;overflow-x:auto;">'
            '<table class="tmpl-table" style="font-size:11px;">'
            f'<thead><tr>{hdr_row}</tr></thead>'
            f'<tbody>{data_rows}</tbody></table></div>',
            unsafe_allow_html=True
        )

    # ── Generate button ───────────────────────────────────────────────────
    if st.button("⚡ Generate All Confirmations", use_container_width=True, key="bulk_gen"):
        from src.auth import log_audit
        username = st.session_state.get("user", {}).get("username", "unknown")

        progress_bar = st.progress(0)
        status_area  = st.empty()
        results      = []
        errors       = []
        zip_buffer   = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, row in enumerate(reader):
                pct = int((i / len(reader)) * 100)
                progress_bar.progress(pct)
                status_area.markdown(
                    f'<div style="font-size:12px;color:rgba(255,255,255,0.5);">'
                    f'Processing row {i+1} of {len(reader)}: '
                    f'<b style="color:#00D4FF">{row.get("counterparty","")}</b> '
                    f'{row.get("trade_type","")}</div>',
                    unsafe_allow_html=True
                )

                # Call generate API
                resp = _api_post_generate({
                    "trade_type":     row.get("trade_type", ""),
                    "counterparty":   row.get("counterparty", ""),
                    "notional_amount":row.get("notional_amount", ""),
                    "currency":       row.get("currency", "USD"),
                    "fixed_rate":     row.get("fixed_rate", ""),
                    "effective_date": row.get("effective_date", ""),
                    "maturity_date":  row.get("maturity_date", ""),
                    "jurisdiction":   row.get("jurisdiction", "US"),
                })

                if "error" in resp:
                    errors.append(f"Row {i+1}: {resp['error']}")
                    continue

                fname = resp.get("output_filename", "")
                if fname:
                    content_bytes = _download_docx(fname)
                    if content_bytes:
                        safe_name = f"confirmation_{i+1:03d}_{row.get('counterparty','trade').replace(' ','_')}.docx"
                        zf.writestr(safe_name, content_bytes)
                        results.append(safe_name)
                    else:
                        errors.append(f"Row {i+1}: Could not download {fname}")
                else:
                    errors.append(f"Row {i+1}: No output file returned")

        progress_bar.progress(100)
        status_area.empty()

        # Results summary
        st.markdown(f"""<div style="display:flex;gap:16px;margin:16px 0;flex-wrap:wrap;">
            <div style="background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.2);
                border-radius:10px;padding:14px 20px;flex:1;">
                <div style="font-size:24px;font-weight:800;color:#00FF88;">{len(results)}</div>
                <div style="font-size:11px;color:rgba(255,255,255,0.4);">Documents Generated</div>
            </div>
            <div style="background:rgba(255,80,80,0.08);border:1px solid rgba(255,80,80,0.2);
                border-radius:10px;padding:14px 20px;flex:1;">
                <div style="font-size:24px;font-weight:800;color:#FF5050;">{len(errors)}</div>
                <div style="font-size:11px;color:rgba(255,255,255,0.4);">Errors</div>
            </div>
        </div>""", unsafe_allow_html=True)

        if errors:
            for err in errors:
                st.markdown(f'<div class="alert alert-error">❌ {err}</div>',
                            unsafe_allow_html=True)

        if results:
            zip_buffer.seek(0)
            log_audit(username, "GENERATE",
                      f"Bulk generation: {len(results)} documents from CSV")
            st.download_button(
                label=f"⬇ Download ZIP ({len(results)} confirmations)",
                data=zip_buffer.getvalue(),
                file_name=f"trade_confirmations_{time.strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                use_container_width=True,
            )
