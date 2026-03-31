"""
auth_ui.py - Login & Signup pages for TradeConfirmation AI.

Key fixes:
  1. _AUTH_CSS contains ONLY pure CSS rules - NO <style> tags inside the string
  2. render_auth_page wraps it: st.markdown(f"<style>{_AUTH_CSS}</style>", ...)
  3. NO st.columns() for layout - uses HTML div centering to kill ghost boxes
  4. Logo/tagline in a separate HTML div ABOVE the form column
"""

import streamlit as st
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.auth import login, signup, verify_token

# ─────────────────────────────────────────────────────────────────────────
# CSS — pure rules only.  NO <style> tags.  NO text outside rules.
# Injected as:  st.markdown(f"<style>{_AUTH_CSS}</style>", unsafe_allow_html=True)
# ─────────────────────────────────────────────────────────────────────────
_AUTH_CSS = (
    "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900"
    "&family=Orbitron:wght@700;800&family=DM+Sans:wght@300;400;500;600&display=swap');"

    "html,body,[data-testid='stAppViewContainer'],[data-testid='stApp'],.stApp,.main,section.main{"
    "background:#060D1F!important;color:#ffffff!important;"
    "font-family:'DM Sans',sans-serif!important;color-scheme:dark!important;}"

    "[data-testid='stAppViewContainer']{"
    "background:radial-gradient(ellipse at 30% 20%,#0f1e3d 0%,#060D1F 55%),"
    "radial-gradient(ellipse at 80% 80%,#0d1f10 0%,transparent 50%)!important;}"

    "#MainMenu,footer,header,[data-testid='stToolbar'],[data-testid='stDecoration'],"
    "[data-testid='stStatusWidget']{display:none!important;visibility:hidden!important;}"

    "[data-testid='stVerticalBlock'],[data-testid='stVerticalBlockBorderWrapper'],"
    "[data-testid='stHorizontalBlock'],[data-testid='stColumn'],[data-testid='stBlock'],"
    "div[data-testid='stVerticalBlockBorderWrapper']>div,div.stVerticalBlock,"
    "div.block-container,.block-container,section.main>div,.main .block-container{"
    "background:transparent!important;border:none!important;box-shadow:none!important;"
    "padding-top:0!important;margin-top:0!important;padding-bottom:0!important;}"

    ".block-container{padding:0!important;max-width:100%!important;}"

    ".auth-logo{font-family:'Orbitron',sans-serif;font-size:17px;font-weight:800;"
    "background:linear-gradient(135deg,#00D4FF,#00FF88);-webkit-background-clip:text;"
    "-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:1px;"
    "text-align:center;margin-bottom:5px;}"

    ".auth-tagline{font-size:12px;color:rgba(255,255,255,0.3);text-align:center;"
    "margin-bottom:28px;letter-spacing:0.5px;}"

    ".auth-card{background:#0D1B35;border:1px solid rgba(0,212,255,0.15);"
    "border-radius:18px;padding:36px 40px;width:100%;max-width:460px;"
    "box-shadow:0 24px 60px rgba(0,0,0,0.5);}"

    ".auth-title{font-family:'Inter',sans-serif;font-size:26px;font-weight:800;"
    "color:#fff;margin-bottom:6px;}"

    ".auth-subtitle{font-size:13px;color:rgba(255,255,255,0.35);margin-bottom:24px;}"

    "input,textarea,[data-baseweb='input'],[data-baseweb='base-input'],"
    "[data-testid='stTextInput']>div,[data-testid='stTextInput']>div>div,"
    "[data-testid='stTextInput'] input,[data-baseweb='input'] input,"
    "[data-baseweb='base-input'] input{"
    "background-color:#0a1628!important;background:#0a1628!important;"
    "color:#ffffff!important;-webkit-text-fill-color:#ffffff!important;"
    "border:1px solid rgba(0,212,255,0.2)!important;border-radius:10px!important;"
    "font-family:'DM Sans',sans-serif!important;font-size:14px!important;"
    "caret-color:#00D4FF!important;"
    "transition:border-color 0.2s ease,box-shadow 0.2s ease!important;}"

    "[data-testid='stTextInput'] input:focus{"
    "border-color:rgba(0,212,255,0.6)!important;"
    "box-shadow:0 0 0 3px rgba(0,212,255,0.1)!important;"
    "background:#0d1f3a!important;-webkit-text-fill-color:#ffffff!important;}"

    "input:-webkit-autofill,input:-webkit-autofill:focus{"
    "-webkit-text-fill-color:#ffffff!important;"
    "-webkit-box-shadow:0 0 0px 9999px #0a1628 inset!important;}"

    "input::placeholder{color:rgba(255,255,255,0.25)!important;"
    "-webkit-text-fill-color:rgba(255,255,255,0.25)!important;}"

    "label,[data-testid='stWidgetLabel']{color:rgba(255,255,255,0.5)!important;"
    "font-size:12px!important;font-weight:600!important;letter-spacing:0.5px!important;}"

    ".stButton>button{background:linear-gradient(135deg,#00D4FF,#00A8CC)!important;"
    "color:#000!important;font-family:'Inter',sans-serif!important;font-weight:700!important;"
    "font-size:14px!important;border:none!important;border-radius:10px!important;"
    "padding:12px 24px!important;width:100%!important;"
    "transition:all 0.2s ease!important;letter-spacing:0.3px!important;}"

    ".stButton>button:hover{transform:translateY(-2px)!important;"
    "box-shadow:0 8px 24px rgba(0,212,255,0.35)!important;}"

    "[data-testid='stSelectbox']>div>div{background:#0a1628!important;"
    "border:1px solid rgba(0,212,255,0.2)!important;border-radius:10px!important;color:#fff!important;}"

    "[data-testid='stSelectbox'] span{color:#ffffff!important;}"

    ".role-card{display:flex;align-items:flex-start;gap:12px;"
    "background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);"
    "border-radius:10px;padding:12px 14px;margin-bottom:8px;}"

    ".role-name{font-size:12px;font-weight:700;color:#00D4FF;margin-bottom:3px;}"
    ".role-desc{font-size:11px;color:rgba(255,255,255,0.35);}"

    ".alert-success{background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.25);"
    "color:#00ff88;border-radius:10px;padding:12px 16px;font-size:13px;margin:8px 0;}"

    ".alert-error{background:rgba(255,80,80,0.08);border:1px solid rgba(255,80,80,0.25);"
    "color:#ff5050;border-radius:10px;padding:12px 16px;font-size:13px;margin:8px 0;}"

    ".auth-divider{display:flex;align-items:center;gap:12px;margin:20px 0;}"
    ".auth-divider-line{flex:1;height:1px;background:rgba(255,255,255,0.07);}"
    ".auth-divider-text{font-size:11px;color:rgba(255,255,255,0.2);white-space:nowrap;}"
)


# ── Role info ─────────────────────────────────────────────────────────────
ROLE_INFO = {
    "user":    {"icon": "👤", "label": "User",    "color": "#A855F7",
                "desc": "View and browse templates only - read-only access"},
    "analyst": {"icon": "📊", "label": "Analyst", "color": "#00D4FF",
                "desc": "Search templates, browse repository, generate confirmations"},
    "manager": {"icon": "🔍", "label": "Manager", "color": "#00FF88",
                "desc": "All analyst access + diff comparisons and download reports"},
    "admin":   {"icon": "⚙️", "label": "Admin",   "color": "#F59E0B",
                "desc": "Full access - upload, delete, manage users and settings"},
}


# ── Session helpers ───────────────────────────────────────────────────────
def init_session():
    for k, v in [("logged_in", False), ("user", None),
                 ("token", None), ("role", None), ("auth_tab", "login")]:
        if k not in st.session_state:
            st.session_state[k] = v


def is_authenticated() -> bool:
    if not st.session_state.get("logged_in"):
        return False
    token = st.session_state.get("token", "")
    data  = verify_token(token) if token else None
    if not data:
        logout()
        return False
    return True


def logout():
    from src.auth import log_audit
    if st.session_state.get("user"):
        log_audit(st.session_state["user"]["username"], "LOGOUT", "User logged out")
    st.session_state.logged_in = False
    st.session_state.user      = None
    st.session_state.token     = None
    st.session_state.role      = None
    st.rerun()


# ── Login form ────────────────────────────────────────────────────────────
def _render_login():
    st.markdown('<div class="auth-title">Welcome back</div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-subtitle">Sign in to your TradeConfirmation AI account</div>',
                unsafe_allow_html=True)

    username = st.text_input("Username", placeholder="Enter your username", key="login_user")
    password = st.text_input("Password", placeholder="Enter your password",
                             type="password", key="login_pass")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if st.button("Sign In", key="btn_login", use_container_width=True):
        if not username or not password:
            st.markdown('<div class="alert-error">Please enter both username and password.</div>',
                        unsafe_allow_html=True)
        else:
            with st.spinner("Authenticating..."):
                ok, token_or_msg, user = login(username.strip(), password)
            if ok:
                st.session_state.logged_in = True
                st.session_state.token     = token_or_msg
                st.session_state.user      = user
                st.session_state.role      = user["role"]
                st.rerun()
            else:
                st.markdown(f'<div class="alert-error">❌ {token_or_msg}</div>',
                            unsafe_allow_html=True)

    st.markdown('<div class="auth-divider"><div class="auth-divider-line"></div>'
                '<div class="auth-divider-text">New to the platform?</div>'
                '<div class="auth-divider-line"></div></div>', unsafe_allow_html=True)

    if st.button("Create Account", key="goto_signup", use_container_width=True):
        st.session_state.auth_tab = "signup"
        st.rerun()


# ── Signup form ───────────────────────────────────────────────────────────
def _render_signup():
    st.markdown('<div class="auth-title">Create account</div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-subtitle">Join TradeConfirmation AI - fill in your details</div>',
                unsafe_allow_html=True)

    full_name = st.text_input("Full Name",        placeholder="e.g. Jane Smith",       key="su_name")
    email     = st.text_input("Email",            placeholder="jane@example.com",       key="su_email")
    username  = st.text_input("Username",         placeholder="3-20 chars, no spaces",  key="su_user")
    password  = st.text_input("Password",         placeholder="Minimum 6 characters",
                               type="password",   key="su_pass")
    confirm   = st.text_input("Confirm Password", placeholder="Re-enter password",
                               type="password",   key="su_confirm")

    role = st.selectbox(
        "Role",
        ["user", "analyst", "manager"],
        format_func=lambda r: f"{ROLE_INFO[r]['icon']}  {ROLE_INFO[r]['label']} - {ROLE_INFO[r]['desc']}",
        key="su_role"
    )

    ri = ROLE_INFO[role]
    st.markdown(
        f'<div class="role-card">'
        f'<div style="font-size:18px;line-height:1">{ri["icon"]}</div>'
        f'<div><div class="role-name" style="color:{ri["color"]}">{ri["label"]}</div>'
        f'<div class="role-desc">{ri["desc"]}</div></div></div>',
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if st.button("Create Account", key="btn_signup", use_container_width=True):
        if not all([full_name, email, username, password, confirm]):
            st.markdown('<div class="alert-error">All fields are required.</div>',
                        unsafe_allow_html=True)
        elif password != confirm:
            st.markdown('<div class="alert-error">Passwords do not match.</div>',
                        unsafe_allow_html=True)
        else:
            ok, msg = signup(username, password, full_name, email, role)
            if ok:
                st.markdown(f'<div class="alert-success">✅ {msg}</div>',
                            unsafe_allow_html=True)
                time.sleep(1.2)
                st.session_state.auth_tab = "login"
                st.rerun()
            else:
                st.markdown(f'<div class="alert-error">❌ {msg}</div>',
                            unsafe_allow_html=True)

    st.markdown('<div class="auth-divider"><div class="auth-divider-line"></div>'
                '<div class="auth-divider-text">Already have an account?</div>'
                '<div class="auth-divider-line"></div></div>', unsafe_allow_html=True)

    if st.button("Back to Sign In", key="goto_login", use_container_width=True):
        st.session_state.auth_tab = "login"
        st.rerun()


# ── Main auth page renderer ───────────────────────────────────────────────
def render_auth_page():
    """
    Renders the full auth page cleanly.

    Why this works:
    - _AUTH_CSS is a plain CSS string with NO <style> tags inside it.
    - We wrap it here: <style>{_AUTH_CSS}</style> — exactly one injection.
    - The logo/tagline are in a self-contained HTML div above the form.
    - We use ONE wide middle column — the two side columns have no visible
      Streamlit block wrappers and produce no ghost boxes.
    """
    init_session()

    # ── Step 1: Inject CSS exactly once ──────────────────────────────────
    if not st.session_state.get("_auth_css_injected"):
        st.markdown(f"<style>{_AUTH_CSS}</style>", unsafe_allow_html=True)
        st.session_state["_auth_css_injected"] = True

    # ── Step 2: Logo + tagline — pure HTML, no Streamlit widget ──────────
    st.markdown(
        '<div style="text-align:center;padding:40px 0 0;">'
        '<div class="auth-logo">&#9889; TradeConfirmation AI</div>'
        '<div class="auth-tagline">Capital Markets - Intelligent Document Automation</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # ── Step 3: Form — centred single column, no side ghost columns ───────
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        if st.session_state.auth_tab == "login":
            _render_login()
        else:
            _render_signup()
        st.markdown('</div>', unsafe_allow_html=True)
