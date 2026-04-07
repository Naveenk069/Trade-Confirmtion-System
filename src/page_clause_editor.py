"""
page_clause_editor.py — Clause Library Editor (P3 Feature).

Admin UI to view, edit, add and delete entries in the approved clause library.
Changes are persisted to data/clause_library.json which overrides the default
APPROVED_CLAUSES in template_populator.py at runtime.
"""

import streamlit as st
import json
from pathlib import Path
from src.auth import log_audit

CLAUSE_FILE = Path(__file__).parent.parent / "data" / "clause_library.json"

# Default structure mirrors APPROVED_CLAUSES in template_populator.py
DEFAULT_LIBRARY = {
    "governing_law": {
        "US":   "New York",
        "UK":   "English",
        "EU":   "English",
        "APAC": "English",
    },
    "isda_version": {
        "Interest Rate Swap":  "2002 ISDA Master Agreement",
        "FX Forward":          "2002 ISDA Master Agreement",
        "Credit Default Swap": "2003 ISDA Credit Derivatives Definitions",
        "Equity Swap":         "2002 ISDA Master Agreement + 2011 Equity Derivatives Definitions",
        "Total Return Swap":   "2002 ISDA Master Agreement",
    },
    "day_count": {
        "USD": "Actual/360",
        "EUR": "Actual/360",
        "GBP": "Actual/365",
        "JPY": "Actual/360",
        "CHF": "Actual/360",
    },
    "floating_rate_benchmark": {
        "USD": "SOFR",
        "GBP": "SONIA",
        "EUR": "EURIBOR",
        "JPY": "TONA",
        "CHF": "SARON",
    },
    "clearing_venue": {
        "Interest Rate Swap":  "LCH SwapClear",
        "Credit Default Swap": "ICE Clear Credit",
        "Equity Swap":         "Not cleared (bilateral)",
        "FX Forward":          "Not cleared (bilateral)",
    },
    "payment_frequency": {
        "Interest Rate Swap":  "Quarterly",
        "FX Forward":          "At maturity",
        "Credit Default Swap": "Quarterly",
        "Equity Swap":         "Quarterly",
    },
}

CATEGORY_LABELS = {
    "governing_law":          "Governing Law  (by Jurisdiction)",
    "isda_version":           "ISDA Version   (by Trade Type)",
    "day_count":              "Day Count Convention  (by Currency)",
    "floating_rate_benchmark":"Floating Rate Benchmark  (by Currency)",
    "clearing_venue":         "Clearing Venue  (by Trade Type)",
    "payment_frequency":      "Payment Frequency  (by Trade Type)",
}

CATEGORY_COLORS = {
    "governing_law":           "#00D4FF",
    "isda_version":            "#A855F7",
    "day_count":               "#00FF88",
    "floating_rate_benchmark": "#F59E0B",
    "clearing_venue":          "#FF5050",
    "payment_frequency":       "#00D4FF",
}


def _load() -> dict:
    CLAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CLAUSE_FILE.exists():
        _save(DEFAULT_LIBRARY)
        return DEFAULT_LIBRARY
    try:
        return json.loads(CLAUSE_FILE.read_text())
    except Exception:
        return DEFAULT_LIBRARY


def _save(lib: dict):
    CLAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CLAUSE_FILE.write_text(json.dumps(lib, indent=2))


def page_clause_editor():
    st.markdown(
        '<div class="page-header">'
        '<div class="page-title">Clause Library <span>Editor</span></div>'
        '<div class="page-subtitle">Edit the approved clause library — changes apply immediately to all future generated documents</div>'
        '</div>',
        unsafe_allow_html=True
    )

    role     = st.session_state.get("role", "analyst")
    username = st.session_state.get("user", {}).get("username", "unknown")
    is_admin = role == "admin"

    lib = _load()

    # ── Stats ──────────────────────────────────────────────────────────────
    total_entries = sum(len(v) for v in lib.values())
    _mr = '<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px;">'
    _mr += f'<div style="flex:1;min-width:130px;padding:18px 16px;border-radius:14px;text-align:center;background:rgba(0,212,255,0.12);border:1px solid rgba(0,212,255,0.3);"><div style="font-size:22px;margin-bottom:6px;">📚</div><div style="font-family:Inter,sans-serif;font-size:28px;font-weight:900;color:#00D4FF;line-height:1;">{len(lib)}</div><div style="font-size:11px;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Clause Categories</div></div>'
    _mr += f'<div style="flex:1;min-width:130px;padding:18px 16px;border-radius:14px;text-align:center;background:rgba(0,255,136,0.12);border:1px solid rgba(0,255,136,0.3);"><div style="font-size:22px;margin-bottom:6px;">📋</div><div style="font-family:Inter,sans-serif;font-size:28px;font-weight:900;color:#00FF88;line-height:1;">{total_entries}</div><div style="font-size:11px;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Total Mappings</div></div>'
    _mr += f'<div style="flex:1;min-width:130px;padding:18px 16px;border-radius:14px;text-align:center;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);"><div style="font-size:22px;margin-bottom:6px;">✏️</div><div style="font-family:Inter,sans-serif;font-size:28px;font-weight:900;color:#F59E0B;line-height:1;">{"Yes" if is_admin else "No"}</div><div style="font-size:11px;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Edit Access</div></div>'
    _mr += '</div>'
    st.markdown(_mr, unsafe_allow_html=True)

    if not is_admin:
        st.markdown(
            '<div class="alert alert-warn">⚠ Read-only view — Admin role required to edit.</div>',
            unsafe_allow_html=True
        )

    # ── Category tabs ──────────────────────────────────────────────────────
    for cat_key, cat_label in CATEGORY_LABELS.items():
        col = CATEGORY_COLORS.get(cat_key, "#00D4FF")
        entries = lib.get(cat_key, {})

        with st.expander(f"  {cat_label}  ({len(entries)} entries)", expanded=False):
            st.markdown(
                f'<div style="font-size:11px;color:{col};font-weight:700;'
                f'letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;">'
                f'{cat_key}</div>',
                unsafe_allow_html=True
            )

            # Existing entries
            to_delete = None
            for key, value in list(entries.items()):
                c1, c2, c3 = st.columns([2, 4, 0.8])
                with c1:
                    st.markdown(
                        f'<div style="padding:10px 0;font-size:13px;'
                        f'font-weight:700;color:{col};">{key}</div>',
                        unsafe_allow_html=True
                    )
                with c2:
                    if is_admin:
                        new_val = st.text_input(
                            f"Value for {key}",
                            value=value,
                            key=f"cl_{cat_key}_{key}",
                            label_visibility="collapsed"
                        )
                        if new_val != value:
                            lib[cat_key][key] = new_val
                            _save(lib)
                            log_audit(username, "ADMIN",
                                      f"Clause updated: {cat_key}.{key} = {new_val}")
                            st.toast(f"✅ Updated {key}", icon="✅")
                    else:
                        st.markdown(
                            f'<div style="padding:10px 0;font-size:12px;'
                            f'color:rgba(255,255,255,0.6);">{value}</div>',
                            unsafe_allow_html=True
                        )
                with c3:
                    if is_admin:
                        if st.button("✕", key=f"del_{cat_key}_{key}",
                                     help=f"Delete {key}"):
                            to_delete = key

            if to_delete:
                del lib[cat_key][to_delete]
                _save(lib)
                log_audit(username, "DELETE",
                          f"Clause deleted: {cat_key}.{to_delete}")
                st.rerun()

            # Add new entry
            if is_admin:
                st.markdown(
                    '<div style="height:1px;background:rgba(255,255,255,0.06);'
                    'margin:12px 0;"></div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    '<div style="font-size:11px;color:rgba(255,255,255,0.3);'
                    'font-weight:700;margin-bottom:8px;">ADD NEW ENTRY</div>',
                    unsafe_allow_html=True
                )
                nc1, nc2, nc3 = st.columns([2, 4, 1])
                with nc1:
                    new_key = st.text_input(
                        "Key (e.g. SGD)",
                        key=f"new_k_{cat_key}",
                        placeholder="Key (e.g. SGD)",
                        label_visibility="collapsed"
                    )
                with nc2:
                    new_val = st.text_input(
                        "Value (e.g. Actual/365)",
                        key=f"new_v_{cat_key}",
                        placeholder="Value (e.g. Actual/365)",
                        label_visibility="collapsed"
                    )
                with nc3:
                    if st.button("Add", key=f"add_{cat_key}"):
                        if new_key and new_val:
                            lib.setdefault(cat_key, {})[new_key.strip()] = new_val.strip()
                            _save(lib)
                            log_audit(username, "ADMIN",
                                      f"Clause added: {cat_key}.{new_key} = {new_val}")
                            st.rerun()
                        else:
                            st.warning("Both key and value are required.")

    # ── Reset to defaults ──────────────────────────────────────────────────
    if is_admin:
        st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:12px;color:rgba(255,80,80,0.6);margin-bottom:8px;">'
            '⚠ Danger Zone</div>',
            unsafe_allow_html=True
        )
        if st.button("↺  Reset to Default Clause Library", key="reset_clauses"):
            _save(DEFAULT_LIBRARY)
            log_audit(username, "ADMIN", "Clause library reset to defaults")
            st.success("Clause library reset to defaults.")
            st.rerun()

    # ── Export ─────────────────────────────────────────────────────────────
    st.download_button(
        "⬇ Export Clause Library as JSON",
        data=json.dumps(lib, indent=2),
        file_name="clause_library.json",
        mime="application/json",
        use_container_width=False,
    )
