"""
page_audit.py — Audit Trail Dashboard + User Management page.

P1 Feature:
  - Full audit log viewer with filters
  - User management (admin only): list users, change roles, delete
  - Live activity stats
"""

import streamlit as st
import time
from src.auth import (
    get_audit_logs, list_users, delete_user,
    change_role, log_audit, ROLE_PERMISSIONS
)

ACTION_COLORS = {
    "LOGIN":    "#00FF88",
    "LOGOUT":   "#6B9EC4",
    "SIGNUP":   "#A855F7",
    "SEARCH":   "#00D4FF",
    "GENERATE": "#00D4FF",
    "DIFF":     "#F59E0B",
    "DOWNLOAD": "#00FF88",
    "UPLOAD":   "#F59E0B",
    "DELETE":   "#FF5050",
    "ADMIN":    "#F59E0B",
}

ROLE_COLORS = {
    "admin":   "#F59E0B",
    "manager": "#00FF88",
    "analyst": "#00D4FF",
}


def _action_badge(action: str) -> str:
    col = ACTION_COLORS.get(action, "#6B9EC4")
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:20px;'
            f'font-size:10px;font-weight:700;letter-spacing:.5px;'
            f'background:rgba({_hex_to_rgb(col)},0.12);'
            f'color:{col};border:1px solid rgba({_hex_to_rgb(col)},0.3);">'
            f'{action}</span>')


def _role_badge(role: str) -> str:
    col = ROLE_COLORS.get(role, "#6B9EC4")
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:20px;'
            f'font-size:10px;font-weight:700;'
            f'background:rgba({_hex_to_rgb(col)},0.12);'
            f'color:{col};border:1px solid rgba({_hex_to_rgb(col)},0.3);">'
            f'{role.upper()}</span>')


def _hex_to_rgb(h: str) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"{r},{g},{b}"


def page_audit():
    st.markdown('<div class="page-header"><div class="page-title">Audit <span>Trail</span></div>'
                '<div class="page-subtitle">Full activity log — every search, generation, login and admin action</div>'
                '</div>', unsafe_allow_html=True)

    role = st.session_state.get("role", "analyst")
    username = st.session_state.get("user", {}).get("username", "")

    logs = get_audit_logs(500)

    # ── Stats row ──────────────────────────────────────────────────────────
    total    = len(logs)
    logins   = sum(1 for l in logs if l["action"] == "LOGIN")
    searches = sum(1 for l in logs if l["action"] == "SEARCH")
    gens     = sum(1 for l in logs if l["action"] == "GENERATE")
    diffs    = sum(1 for l in logs if l["action"] == "DIFF")

    st.markdown(f"""<div class="metric-row">
        <div class="metric-card mc-cyan">
            <div class="metric-icon">📋</div>
            <div class="metric-value">{total}</div>
            <div class="metric-label">Total Events</div>
        </div>
        <div class="metric-card mc-green">
            <div class="metric-icon">🔐</div>
            <div class="metric-value">{logins}</div>
            <div class="metric-label">Logins</div>
        </div>
        <div class="metric-card mc-amber">
            <div class="metric-icon">🔍</div>
            <div class="metric-value">{searches}</div>
            <div class="metric-label">Searches</div>
        </div>
        <div class="metric-card mc-purple">
            <div class="metric-icon">🚀</div>
            <div class="metric-value">{gens}</div>
            <div class="metric-label">Generations</div>
        </div>
        <div class="metric-card mc-cyan">
            <div class="metric-icon">⚡</div>
            <div class="metric-value">{diffs}</div>
            <div class="metric-label">Diff Runs</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Filters ────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        actions = ["All"] + sorted({l["action"] for l in logs})
        f_action = st.selectbox("Filter by Action", actions, key="audit_action")
    with col2:
        users = ["All"] + sorted({l["username"] for l in logs})
        f_user = st.selectbox("Filter by User", users, key="audit_user")
    with col3:
        limit = st.number_input("Show entries", 10, 500, 50, key="audit_limit")

    filtered = logs
    if f_action != "All":
        filtered = [l for l in filtered if l["action"] == f_action]
    if f_user != "All":
        filtered = [l for l in filtered if l["username"] == f_user]
    filtered = filtered[:int(limit)]

    # ── Log table ──────────────────────────────────────────────────────────
    if not filtered:
        st.markdown('<div class="alert alert-info">No audit events match your filters.</div>',
                    unsafe_allow_html=True)
    else:
        rows = ""
        for entry in filtered:
            rows += (
                f'<tr>'
                f'<td style="color:rgba(255,255,255,0.45);font-size:11px;">{entry["datetime"]}</td>'
                f'<td style="color:#00D4FF;font-weight:600;">{entry["username"]}</td>'
                f'<td>{_action_badge(entry["action"])}</td>'
                f'<td style="color:rgba(255,255,255,0.55);font-size:12px;">{entry.get("detail","")}</td>'
                f'</tr>'
            )
        table_html = (
            '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
            'border-radius:14px;overflow:hidden;overflow-x:auto;">'
            '<table class="tmpl-table" style="font-size:12px;">'
            '<thead><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Detail</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )
        st.markdown(table_html, unsafe_allow_html=True)

    # ── User Management (Admin only) ────────────────────────────────────────
    if role == "admin":
        st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="page-title" style="font-size:24px;">User <span>Management</span></div>',
                    unsafe_allow_html=True)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        users_list = list_users()
        if not users_list:
            st.markdown('<div class="alert alert-info">No users found.</div>', unsafe_allow_html=True)
            return

        for u in users_list:
            col1, col2, col3, col4 = st.columns([2.5, 1.5, 1.5, 1])
            with col1:
                st.markdown(
                    f'<div style="padding:8px 0;">'
                    f'<div style="font-size:13px;font-weight:700;color:#fff;">'
                    f'{u["full_name"]} &nbsp;'
                    f'<span style="font-size:11px;color:rgba(255,255,255,0.3);">@{u["username"]}</span>'
                    f'</div>'
                    f'<div style="font-size:11px;color:rgba(255,255,255,0.3);margin-top:2px;">'
                    f'{u.get("email","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    f'<div style="padding:14px 0;">{_role_badge(u["role"])}</div>',
                    unsafe_allow_html=True
                )
            with col3:
                if u["username"] != "admin":
                    new_role = st.selectbox(
                        "Change role", ["analyst", "manager", "admin"],
                        index=["analyst","manager","admin"].index(u["role"]),
                        key=f"role_{u['username']}"
                    )
                    if new_role != u["role"]:
                        if change_role(u["username"], new_role):
                            log_audit(username, "ADMIN",
                                      f"Changed {u['username']} role: {u['role']} → {new_role}")
                            st.rerun()
            with col4:
                if u["username"] != "admin" and u["username"] != username:
                    if st.button("Remove", key=f"del_{u['username']}"):
                        delete_user(u["username"])
                        log_audit(username, "DELETE", f"Deleted user: {u['username']}")
                        st.rerun()

            st.markdown('<div style="height:1px;background:rgba(255,255,255,0.05);margin:4px 0;"></div>',
                        unsafe_allow_html=True)
