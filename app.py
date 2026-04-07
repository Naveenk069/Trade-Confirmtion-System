"""
app.py — Streamlit UI for Trade Confirmation Template Search System.

Run with:
    streamlit run app.py

Requires the FastAPI backend running at http://localhost:8000
    uvicorn src.api.main:app --reload --port 8000
"""

import streamlit as st
import requests
import time
from datetime import datetime
from pages_iter2_iter3 import page_diff, page_generate
from src.auth_ui import render_auth_page, init_session, is_authenticated, logout, ROLE_INFO
from src.auth import log_audit, can_access
from src.page_audit import page_audit
from src.page_bulk import page_bulk
from src.page_sidebyside import page_sidebyside
from src.page_heatmap import page_heatmap
from src.page_versions import page_versions
from src.page_clause_editor import page_clause_editor
from src.page_recommender import page_recommender
from src.page_email import page_email

# ─── Config ───────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="TradeConfirmation AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Global CSS (embedded inline - no file I/O, works on all OS) --------

_MASTER_CSS = r"""
/* TradeConfirmation AI -- Master Stylesheet v4.0 */
/* Loaded ONCE via st.markdown -- never re-injected on re-render */

@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;800;900&family=Inter:wght@400;500;600;700;800;900&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ==============================================
   KEYFRAMES
============================================== */
@keyframes fadeUp   { from{opacity:0;transform:translateY(20px) scale(.97)} to{opacity:1;transform:none} }
@keyframes fadeIn   { from{opacity:0} to{opacity:1} }
@keyframes slideIn  { from{opacity:0;transform:translateX(-20px)} to{opacity:1;transform:none} }
@keyframes float    { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)} }
@keyframes pulse    { 0%,100%{box-shadow:0 0 0 0 rgba(0,212,255,0)} 60%{box-shadow:0 0 0 6px rgba(0,212,255,.14)} }
@keyframes shimmer  { from{background-position:-600px 0} to{background-position:600px 0} }
@keyframes scanLine { from{top:-4px} to{top:100%} }
@keyframes glow     { 0%,100%{text-shadow:0 0 10px rgba(0,212,255,.3)} 50%{text-shadow:0 0 24px rgba(0,212,255,.7),0 0 40px rgba(0,255,136,.2)} }
@keyframes barFill  { from{width:0} to{width:var(--w,100%)} }
@keyframes bounce   { 0%,100%{transform:translateY(0)} 45%{transform:translateY(-4px)} }
@keyframes spin     { to{transform:rotate(360deg)} }
@keyframes countUp  { from{opacity:0;transform:translateY(8px) scale(.9)} to{opacity:1;transform:none} }
@keyframes cardIn   { from{opacity:0;transform:perspective(700px) rotateX(6deg) translateY(18px)} to{opacity:1;transform:perspective(700px) rotateX(0) translateY(0)} }

/* ==============================================
   BASE & RESET
============================================== */
*,*::before,*::after{box-sizing:border-box;margin:0}

html,body,[data-testid="stAppViewContainer"]{
  background:#070c18!important;
  font-family:'DM Sans',sans-serif;
  color:#fff;
  -webkit-font-smoothing:antialiased;
}
[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(ellipse at 18% 0%,#0f1d3a 0%,transparent 55%),
    radial-gradient(ellipse at 82% 100%,#0c1e10 0%,transparent 55%),
    #070c18!important;
  animation:fadeIn .4s ease both;
}

/* Remove ALL Streamlit default padding & borders */
.block-container,.main,.stMainBlockContainer{
  padding-top:0!important;
  padding-bottom:0!important;
  max-width:100%!important;
}
[data-testid="stVerticalBlock"],[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stHorizontalBlock"],[data-testid="stColumn"],
[data-testid="stBlock"],[data-testid="stForm"],
div[data-testid="stVerticalBlockBorderWrapper"]>div{
  background:transparent!important;
  border:none!important;
  box-shadow:none!important;
}

/* Hide chrome */
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stDecoration"]{
  display:none!important;
  visibility:hidden!important;
}

/* ==============================================
   ANIMATED BACKGROUND ORBS
============================================== */
[data-testid="stAppViewContainer"]::before{
  content:'';position:fixed;
  width:320px;height:320px;
  background:radial-gradient(circle,rgba(0,212,255,.07) 0%,transparent 70%);
  top:8%;left:12%;border-radius:50%;
  animation:float 9s ease-in-out infinite;
  pointer-events:none;z-index:0;
}
[data-testid="stAppViewContainer"]::after{
  content:'';position:fixed;
  width:240px;height:240px;
  background:radial-gradient(circle,rgba(0,255,136,.05) 0%,transparent 70%);
  bottom:15%;right:8%;border-radius:50%;
  animation:float 12s ease-in-out infinite reverse;
  pointer-events:none;z-index:0;
}

/* ==============================================
   PAGE ENTRY -- stagger children
============================================== */
[data-testid="stVerticalBlock"]>div{
  animation:fadeUp .42s cubic-bezier(.22,1,.36,1) both;
}
[data-testid="stVerticalBlock"]>div:nth-child(1){animation-delay:.00s}
[data-testid="stVerticalBlock"]>div:nth-child(2){animation-delay:.06s}
[data-testid="stVerticalBlock"]>div:nth-child(3){animation-delay:.10s}
[data-testid="stVerticalBlock"]>div:nth-child(4){animation-delay:.14s}
[data-testid="stVerticalBlock"]>div:nth-child(n+5){animation-delay:.18s}

/* ==============================================
   SIDEBAR
============================================== */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#090e1c 0%,#050910 100%)!important;
  border-right:1px solid rgba(255,255,255,.06)!important;
  animation:slideIn .38s cubic-bezier(.22,1,.36,1) both;
  will-change:transform;
  transform:translateZ(0);
}
[data-testid="stSidebar"]>div{padding-top:0!important}

/* ==============================================
   LOGO
============================================== */
.logo-wrap{padding:22px 16px 20px;border-bottom:1px solid rgba(255,255,255,.06);margin-bottom:12px}
.logo-text{
  font-family:'Orbitron',sans-serif;font-size:13px;font-weight:800;
  background:linear-gradient(135deg,#00d4ff,#00ff88);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;letter-spacing:.5px;white-space:nowrap;
  animation:glow 3s ease-in-out infinite;
}
.logo-sub{font-size:10px;color:rgba(255,255,255,.3);letter-spacing:2px;text-transform:uppercase;margin-top:5px;font-family:'DM Sans',sans-serif}

/* ==============================================
   STATUS PILLS
============================================== */
.status-pill{display:inline-flex;align-items:center;gap:8px;padding:7px 14px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:.5px}
.status-online{background:rgba(0,255,136,.1);border:1px solid rgba(0,255,136,.3);color:#00ff88;animation:pulse 2.5s ease-in-out infinite}
.status-offline{background:rgba(255,80,80,.1);border:1px solid rgba(255,80,80,.3);color:#ff5050}
.status-dot{width:7px;height:7px;border-radius:50%}
.dot-green{background:#00ff88;box-shadow:0 0 6px #00ff88;animation:pulse 1.8s ease-in-out infinite}
.dot-red{background:#ff5050}

/* ==============================================
   BUTTONS
============================================== */
.stButton>button{
  background:linear-gradient(135deg,#00d4ff,#00a8cc)!important;
  color:#000!important;font-family:'Inter',sans-serif!important;
  font-weight:700!important;font-size:13px!important;
  border:none!important;border-radius:10px!important;
  padding:10px 22px!important;
  transition:transform .2s cubic-bezier(.34,1.56,.64,1),
             box-shadow .2s ease,opacity .15s ease!important;
  position:relative!important;overflow:hidden!important;
  will-change:transform;
}
.stButton>button::after{
  content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,.18) 50%,transparent 100%);
  transform:translateX(-100%);
  transition:transform .5s ease;
}
.stButton>button:hover{
  transform:translateY(-3px) scale(1.02)!important;
  box-shadow:0 10px 28px rgba(0,212,255,.38),0 4px 8px rgba(0,0,0,.3)!important;
}
.stButton>button:hover::after{transform:translateX(100%)}
.stButton>button:active{transform:translateY(0) scale(.97)!important;transition-duration:.08s!important}

/* ==============================================
   PAGE HEADER
============================================== */
.page-header{padding:36px 0 28px;border-bottom:1px solid rgba(255,255,255,.06);margin-bottom:32px;animation:fadeUp .5s cubic-bezier(.22,1,.36,1) both}
.page-title{font-family:'Inter',sans-serif;font-size:40px;font-weight:900;color:#fff;letter-spacing:-1.5px;line-height:1.1}
.page-title span{font-family:'Inter',sans-serif;font-weight:900;background:linear-gradient(135deg,#00d4ff,#00ff88);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.page-subtitle{font-size:15px;color:rgba(255,255,255,.4);margin-top:6px}

/* ==============================================
   METRIC CARDS
============================================== */
.metric-row{display:flex;gap:16px;margin-bottom:32px;flex-wrap:wrap}
.metric-card{
  flex:1;min-width:140px;padding:20px 18px;border-radius:14px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
  transition:transform .25s cubic-bezier(.34,1.56,.64,1),box-shadow .25s ease;
  animation:countUp .6s cubic-bezier(.22,1,.36,1) both,float 7s ease-in-out infinite;
  will-change:transform;
}
.metric-card:nth-child(2){animation-delay:.08s,1.5s}
.metric-card:nth-child(3){animation-delay:.14s,3s}
.metric-card:nth-child(4){animation-delay:.20s,4.5s}
.metric-card:hover{transform:translateY(-6px) scale(1.03)!important;box-shadow:0 20px 44px rgba(0,212,255,.18)!important;animation-play-state:running,paused}
.metric-icon{font-size:20px;margin-bottom:10px}
.metric-value{font-family:'Inter',sans-serif;font-size:32px;font-weight:900;color:#fff;line-height:1}
.metric-label{font-size:11px;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.mc-cyan{border-color:rgba(0,212,255,.2)!important}
.mc-green{border-color:rgba(0,255,136,.2)!important}
.mc-amber{border-color:rgba(245,158,11,.2)!important}
.mc-purple{border-color:rgba(168,85,247,.2)!important}
.mc-red{border-color:rgba(255,80,80,.2)!important}

/* ==============================================
   RESULT CARDS
============================================== */
.result-card{
  background:#0d1b35;border:1px solid rgba(255,255,255,.07);
  border-radius:14px;padding:22px 22px 16px;margin-bottom:16px;
  position:relative;overflow:hidden;
  animation:cardIn .45s cubic-bezier(.22,1,.36,1) both;
  transition:transform .25s cubic-bezier(.34,1.56,.64,1),
             box-shadow .25s ease,border-color .2s ease;
  will-change:transform;
  contain:layout style;
}
.result-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,#00d4ff,#00ff88);
  transform:scaleX(0);transform-origin:left;
  transition:transform .3s ease;
}
.result-card:hover{transform:translateY(-5px) scale(1.008)!important;box-shadow:0 20px 44px rgba(0,212,255,.16),0 8px 16px rgba(0,0,0,.35)!important;border-color:rgba(0,212,255,.2)!important}
.result-card:hover::before{transform:scaleX(1)}
.rank-badge{position:absolute;top:12px;right:14px;font-size:11px;font-weight:700;color:rgba(255,255,255,.25);font-family:'Inter',sans-serif}
.result-filename{font-family:'Inter',sans-serif;font-size:14px;font-weight:700;color:#fff;margin-bottom:14px}

/* ==============================================
   SCORE BAR
============================================== */
.score-wrap{margin-bottom:14px}
.score-label{display:flex;justify-content:space-between;align-items:center;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:6px}
.score-bar-bg{height:6px;background:rgba(255,255,255,.07);border-radius:3px;overflow:hidden}
.score-bar-fill{height:100%;border-radius:3px;animation:barFill 1s cubic-bezier(.4,0,.2,1) .3s both}

/* ==============================================
   BADGES
============================================== */
.badge-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;background:rgba(255,255,255,.06);color:rgba(255,255,255,.6);border:1px solid rgba(255,255,255,.1);transition:transform .2s cubic-bezier(.34,1.56,.64,1),background .2s ease;animation:bounce .5s ease both}
.badge:hover{transform:translateY(-2px) scale(1.08);background:rgba(255,255,255,.1)}
.badge-trade{background:rgba(0,212,255,.1);color:#00d4ff;border-color:rgba(0,212,255,.2)}
.badge-cp{background:rgba(168,85,247,.1);color:#a855f7;border-color:rgba(168,85,247,.2)}
.badge-jur{background:rgba(0,255,136,.1);color:#00ff88;border-color:rgba(0,255,136,.2)}
.badge-prod{background:rgba(245,158,11,.1);color:#f59e0b;border-color:rgba(245,158,11,.2)}
.badge-ver{background:rgba(255,255,255,.05);color:rgba(255,255,255,.4)}
.badge-active{background:rgba(0,255,136,.12);color:#00ff88;border-color:rgba(0,255,136,.25)}
.badge-draft{background:rgba(245,158,11,.12);color:#f59e0b;border-color:rgba(245,158,11,.25)}
.badge-deprecated{background:rgba(255,80,80,.12);color:#ff5050;border-color:rgba(255,80,80,.25)}

/* ==============================================
   SNIPPET
============================================== */
.result-snippet{font-size:12px;color:rgba(255,255,255,.45);line-height:1.6;margin-bottom:6px}

/* ==============================================
   SEARCH WRAP
============================================== */
.search-wrap{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px 20px;margin-bottom:16px;transition:border-color .2s ease}
.search-wrap:focus-within{border-color:rgba(0,212,255,.3)!important;box-shadow:0 0 0 3px rgba(0,212,255,.06)}
.search-label{font-size:11px;font-weight:700;color:rgba(255,255,255,.3);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px}

/* ==============================================
   FILTER SECTION
============================================== */
.filter-section{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:12px;padding:14px 18px;margin-bottom:16px}
.filter-title{font-size:10px;font-weight:700;color:rgba(255,255,255,.25);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px}

/* ==============================================
   INPUTS -- dark + animated focus
============================================== */
[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="textarea"],
[data-testid="stTextInput"]>div,[data-testid="stTextInput"]>div>div,
[data-testid="stTextArea"]>div,[data-testid="stTextArea"]>div>div{
  background-color:#0d1b35!important;background:#0d1b35!important;
}
input,textarea,
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,
[data-baseweb="input"] input,[data-baseweb="base-input"] input{
  background-color:#0d1b35!important;background:#0d1b35!important;
  color:#fff!important;-webkit-text-fill-color:#fff!important;
  border:1px solid rgba(0,212,255,.25)!important;border-radius:10px!important;
  font-family:'DM Sans',sans-serif!important;font-size:14px!important;
  caret-color:#00d4ff!important;
  transition:border-color .18s ease,box-shadow .18s ease,transform .15s ease!important;
}
input:focus,textarea:focus,
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{
  background:#122540!important;-webkit-text-fill-color:#fff!important;
  border-color:rgba(0,212,255,.65)!important;
  box-shadow:0 0 0 3px rgba(0,212,255,.1),0 0 18px rgba(0,212,255,.07)!important;
  transform:translateY(-1px)!important;outline:none!important;
}
input::placeholder,textarea::placeholder{color:rgba(255,255,255,.25)!important;-webkit-text-fill-color:rgba(255,255,255,.25)!important}
input:-webkit-autofill,input:-webkit-autofill:focus{
  -webkit-text-fill-color:#fff!important;
  -webkit-box-shadow:0 0 0 9999px #0d1b35 inset!important;
}

/* ==============================================
   SELECTBOX
============================================== */
[data-testid="stSelectbox"]>div>div,[data-testid="stMultiSelect"]>div>div{
  background:rgba(255,255,255,.05)!important;border:1px solid rgba(255,255,255,.1)!important;
  border-radius:10px!important;color:#fff!important;
  transition:border-color .18s ease,box-shadow .18s ease!important;
}
[data-testid="stSelectbox"]>div>div:hover{border-color:rgba(0,212,255,.4)!important}
[data-testid="stSelectbox"] span,[data-testid="stMultiSelect"] span{color:#fff!important}
label,[data-testid="stWidgetLabel"]{
  color:rgba(255,255,255,.5)!important;font-size:12px!important;
  font-weight:500!important;letter-spacing:.5px!important;
  font-family:'DM Sans',sans-serif!important;
}
[data-testid="stNumberInput"] input{background:#0d1b35!important;border:1px solid rgba(0,212,255,.25)!important;border-radius:10px!important;color:#fff!important;-webkit-text-fill-color:#fff!important}
[data-testid="stFileUploader"]{background:rgba(255,255,255,.03)!important;border:1px dashed rgba(0,212,255,.25)!important;border-radius:12px!important;transition:border-color .2s ease,background .2s ease!important}
[data-testid="stFileUploader"]:hover{border-color:rgba(0,212,255,.5)!important;background:rgba(0,212,255,.03)!important}
[data-testid="stCheckbox"] label{color:rgba(255,255,255,.6)!important}
div[data-testid="stExpander"]{background:rgba(255,255,255,.02)!important;border:1px solid rgba(255,255,255,.07)!important;border-radius:12px!important;transition:border-color .2s ease!important}
div[data-testid="stExpander"]:hover{border-color:rgba(0,212,255,.2)!important}
[data-testid="stRadio"] label{color:rgba(255,255,255,.75)!important}

/* ==============================================
   TEMPLATE TABLE
============================================== */
.tmpl-table{width:100%;border-collapse:collapse;font-family:'DM Sans',sans-serif}
.tmpl-table th{font-size:10px;font-weight:700;color:rgba(255,255,255,.3);letter-spacing:1.2px;text-transform:uppercase;padding:10px 14px;background:rgba(255,255,255,.03);border-bottom:1px solid rgba(255,255,255,.07)}
.tmpl-table td{padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.04);font-size:13px;transition:background .15s ease}
.tmpl-table tr:hover td{background:rgba(0,212,255,.04)!important}
.tmpl-filename{font-family:'DM Sans',sans-serif;font-size:12px;font-weight:600;color:rgba(255,255,255,.85)}

/* ==============================================
   DIFF CARDS
============================================== */
.disc-card{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:16px 18px;margin-bottom:12px;transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease;animation:fadeUp .4s cubic-bezier(.22,1,.36,1) both;contain:layout style}
.disc-card:hover{transform:translateX(5px)!important;border-color:rgba(0,212,255,.2)!important;box-shadow:-4px 0 18px rgba(0,212,255,.12)!important}
.disc-field{font-family:'DM Sans',sans-serif;font-size:15px;font-weight:700;color:#fff}
.disc-cat{font-size:10px;font-weight:700;color:rgba(255,255,255,.3);letter-spacing:.8px;text-transform:uppercase;background:rgba(255,255,255,.06);padding:2px 8px;border-radius:10px}
.disc-values{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.disc-val-box{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:10px 12px}
.disc-val-label{font-size:10px;color:rgba(255,255,255,.35);font-weight:700;letter-spacing:.8px;text-transform:uppercase;margin-bottom:4px}
.disc-val-text{font-size:13px;color:rgba(255,255,255,.8);word-break:break-word}
.disc-explain{font-size:12px;color:rgba(255,255,255,.35);margin-top:10px;font-style:italic}
.risk-badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:.5px;transition:transform .2s cubic-bezier(.34,1.56,.64,1)}
.risk-badge:hover{transform:scale(1.1)}
.rb-HIGH{background:rgba(255,80,80,.15);color:#ff5050;border:1px solid rgba(255,80,80,.3)}
.rb-MEDIUM{background:rgba(251,191,36,.15);color:#fbbf24;border:1px solid rgba(251,191,36,.3)}
.rb-LOW{background:rgba(0,255,136,.15);color:#00ff88;border:1px solid rgba(0,255,136,.3)}

/* ==============================================
   SCORE RING
============================================== */
.score-ring-wrap{text-align:center;padding:8px 16px}
.score-number{font-family:'Inter',sans-serif;font-size:52px;font-weight:900;line-height:1;animation:countUp .7s cubic-bezier(.22,1,.36,1) both}
.score-label{font-size:11px;color:rgba(255,255,255,.35);letter-spacing:.8px;text-transform:uppercase;margin-top:4px}

/* ==============================================
   ALERTS
============================================== */
.alert{padding:14px 18px;border-radius:10px;font-size:13px;margin:12px 0;display:flex;align-items:center;gap:10px;animation:fadeUp .35s ease both}
.alert-success{background:rgba(0,255,136,.08);border:1px solid rgba(0,255,136,.2);color:#00ff88}
.alert-error{background:rgba(255,80,80,.08);border:1px solid rgba(255,80,80,.2);color:#ff5050}
.alert-info{background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.2);color:#00d4ff}
.alert-warn{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);color:#fbbf24}

/* ==============================================
   UPLOAD ZONE
============================================== */
.upload-zone{border:2px dashed rgba(0,212,255,.2);border-radius:14px;padding:32px;text-align:center;background:rgba(0,212,255,.02);transition:border-color .2s ease,background .2s ease;margin-bottom:24px}
.upload-zone:hover{border-color:rgba(0,212,255,.4);background:rgba(0,212,255,.05)}
.upload-icon{font-size:48px;margin-bottom:12px}
.upload-title{font-family:'Inter',sans-serif;font-size:18px;font-weight:700;color:#fff;margin-bottom:6px}
.upload-sub{font-size:13px;color:rgba(255,255,255,.35)}

/* ==============================================
   GRADIENT DIVIDER
============================================== */
.grad-divider{height:1px;background:linear-gradient(90deg,transparent,rgba(0,212,255,.3),transparent);margin:28px 0}

/* ==============================================
   SHIMMER LOADING SKELETON
============================================== */
.skeleton{background:linear-gradient(90deg,rgba(255,255,255,.04) 25%,rgba(0,212,255,.09) 50%,rgba(255,255,255,.04) 75%);background-size:600px 100%;animation:shimmer 1.6s ease-in-out infinite;border-radius:8px}

/* ==============================================
   SPINNER -- faster
============================================== */
.stSpinner>div{animation-duration:.55s!important}

/* ==============================================
   SCROLLBAR
============================================== */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(0,212,255,.25);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:rgba(0,212,255,.45)}

/* == FORCE DARK MODE - prevents light theme override == */
html, html[data-theme="light"], html[data-theme="dark"],
body, body[data-theme="light"],
[data-testid="stApp"], [data-testid="stAppViewContainer"],
[data-testid="stMain"], section.main,
.main, .stApp {
    background: #070c18 !important;
    color: #ffffff !important;
    color-scheme: dark !important;
}

/* == Missing colour classes == */
.mc-blue { border-color:rgba(0,212,255,.2)!important; }

/* == Force all text white == */
p, span, div, h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span {
    color: rgba(255,255,255,0.85);
}

/* == Page title always white == */
.page-header, .page-title { color:#ffffff !important; }
.page-subtitle { color:rgba(255,255,255,0.45) !important; }

/* == Metric card values always white == */
.metric-value { color:#ffffff !important; }
.metric-label { color:rgba(255,255,255,0.4) !important; }
.metric-icon  { color:#ffffff !important; }

/* == Version control cards == */
[data-testid="stMarkdownContainer"] { color:rgba(255,255,255,0.8) !important; }

/* == All markdown text == */
.stMarkdown, .stMarkdown p, .stMarkdown span,
.stMarkdown li, .stMarkdown h1, .stMarkdown h2,
.stMarkdown h3, .stMarkdown h4 {
    color: rgba(255,255,255,0.85) !important;
}

/* == Expander content text == */
div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] p {
    color: rgba(255,255,255,0.75) !important;
}

/* == Fix all link colors == */
a { color: #00d4ff !important; }

/* == Force sidebar text white == */
[data-testid="stSidebar"] * { color: rgba(255,255,255,0.85) !important; }
[data-testid="stSidebar"] .logo-text { color: transparent !important; }

/* == Animated underline on page titles == */
.page-title::after {
    content: '';
    display: block;
    width: 60px; height: 3px;
    background: linear-gradient(90deg, #00d4ff, #00ff88);
    border-radius: 2px;
    margin-top: 8px;
    animation: barFill 0.8s cubic-bezier(.4,0,.2,1) .5s both;
    --w: 60px;
}

/* == Glowing active nav button == */
[data-testid="stSidebar"] button:focus,
[data-testid="stSidebar"] button:active {
    background: rgba(0,212,255,0.15) !important;
    border-left: 3px solid #00d4ff !important;
    box-shadow: inset 3px 0 12px rgba(0,212,255,0.1) !important;
}

"""
def _inject_css():
    """Inject CSS once per session only."""
    if st.session_state.get("_css_ok"):
        return
    st.markdown(f"<style>{_MASTER_CSS}</style>", unsafe_allow_html=True)
    st.session_state["_css_ok"] = True


# ─── API helpers ──────────────────────────────────────────────────────────

@st.cache_data(ttl=60)           # cache GET responses for 60s
def api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=4)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=8)            # health check cached 8s
def _cached_health() -> tuple[bool, dict]:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=2)
        if r.status_code == 200:
            return True, r.json()
    except Exception:
        pass
    return False, {}


def api_post(path: str, payload: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def api_delete(path: str) -> dict | None:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=4)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def check_api() -> tuple[bool, dict]:
    return _cached_health()


def score_color(score: float) -> str:
    if score >= 0.4:   return "linear-gradient(90deg, #00ff88, #00d4ff)"
    if score >= 0.25:  return "linear-gradient(90deg, #fbbf24, #f59e0b)"
    return                    "linear-gradient(90deg, #f87171, #ef4444)"


def status_badge(status: str) -> str:
    cls = {"active": "badge-active", "draft": "badge-draft"}.get(status, "badge-deprecated")
    icon = {"active": "●", "draft": "◐"}.get(status, "○")
    return f'<span class="badge {cls}">{icon} {status.upper()}</span>'


# ─── Sidebar ──────────────────────────────────────────────────────────────

def render_sidebar():
    user = st.session_state.get("user", {}) or {}
    role = st.session_state.get("role", "analyst")
    username = user.get("username", "")
    full_name = user.get("full_name", username)

    role_colors = {"admin": "#F59E0B", "manager": "#00FF88", "analyst": "#00D4FF"}
    role_col = role_colors.get(role, "#00D4FF")

    with st.sidebar:
        # Logo
        st.markdown("""<div class="logo-wrap">
    <div class="logo-text">⚡ TradeConfirmation AI</div>
</div>""", unsafe_allow_html=True)

        # User info card
        st.markdown(f"""<div style="margin:0 0 16px;padding:12px 16px;
            background:rgba(255,255,255,0.03);border-radius:10px;
            border:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:13px;font-weight:700;color:#fff;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {full_name}
            </div>
            <div style="margin-top:4px;display:flex;align-items:center;gap:8px;">
                <span style="display:inline-block;padding:2px 8px;border-radius:20px;
                    font-size:10px;font-weight:700;
                    background:rgba({','.join(str(int(role_col.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.15);
                    color:{role_col};border:1px solid rgba({','.join(str(int(role_col.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.3);">
                    {role.upper()}
                </span>
                <span style="font-size:10px;color:rgba(255,255,255,0.25);">@{username}</span>
            </div>
        </div>""", unsafe_allow_html=True)

        # API status
        online, health = check_api()
        if online:
            count   = health.get("templates_in_store", 0)
            backend = health.get("embedding_backend", "")
            st.markdown(f"""<div style="padding:0 0 16px;">
    <div class="status-pill status-online">
        <div class="status-dot dot-green"></div> API ONLINE
    </div>
    <div style="margin-top:8px;font-size:11px;color:rgba(255,255,255,0.25);">
        {count} templates &nbsp;·&nbsp; {backend}
    </div>
</div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div style="padding:0 0 16px;">
    <div class="status-pill status-offline">
        <div class="status-dot dot-red"></div> API OFFLINE
    </div>
    <div style="margin-top:6px;font-size:10px;color:rgba(255,80,80,0.5);">
        uvicorn src.api.main:app
    </div>
</div>""", unsafe_allow_html=True)

        # Navigation — strictly role-gated per permission
        if "page" not in st.session_state:
            st.session_state.page = "search"

        nav_items = [
            # ── User + above (4 core pages) ──────────────────────
            ("📋", "Template Browser",    "browser",    True),
            ("🔍", "Search Templates",    "search",     can_access(role, "search")),
            ("⚡", "Diff Highlighter",    "diff",       can_access(role, "diff")),
            ("🚀", "Generate Template",   "generate",   can_access(role, "generate")),

            # ── Analyst + above ──────────────────────────────────
            ("💡", "Smart Recommender",   "recommender",can_access(role, "recommender")),
            ("📦", "Bulk Generation",     "bulk",       can_access(role, "generate") and role != "user"),
            ("📧", "Email Notification",  "email",      can_access(role, "generate") and role != "user"),

            # ── Manager + above ──────────────────────────────────
            ("🪟", "Side-by-Side Viewer", "sidebyside", can_access(role, "sidebyside")),
            ("🌡", "Risk Heatmap",        "heatmap",    can_access(role, "heatmap")),
            ("🗂", "Version Control",     "versions",   can_access(role, "versions")),

            # ── Admin only ───────────────────────────────────────
            ("📚", "Clause Library",      "clauses",    can_access(role, "clauses")),
            ("⬆️", "Upload Template",     "upload",     can_access(role, "upload")),
            ("📊", "Audit Trail",         "audit",      can_access(role, "audit")),
            ("⚙️", "Admin Panel",         "admin",      can_access(role, "admin")),
        ]

        for icon, label, key, allowed in nav_items:
            if allowed:
                if st.button(f"{icon}  {label}", key=f"nav_{key}",
                             use_container_width=True):
                    log_audit(username, label.upper().split()[0],
                              f"Navigated to {label}")
                    st.session_state.page = key
                    st.rerun()

        # Logout button
        st.markdown('<div style="margin-top:16px;border-top:1px solid rgba(255,255,255,0.06);padding-top:12px;"></div>',
                    unsafe_allow_html=True)
        if st.button("🚪  Sign Out", key="nav_logout", use_container_width=True):
            logout()

    return st.session_state.page


# ─── Page: Search ─────────────────────────────────────────────────────────

def page_search():
    st.markdown("""<div class="page-header">
    <div class="page-title">Semantic <span>Template Search</span></div>
    <div class="page-subtitle">Find the most relevant confirmation template using AI-powered search</div>
</div>""", unsafe_allow_html=True)

    # Load facets for filters
    facets = api_get("/facets") or {}
    trade_types   = ["All"] + facets.get("trade_types", [])
    jurisdictions = ["All"] + facets.get("jurisdictions", [])
    products      = ["All"] + facets.get("products", [])

    # Search box
    st.markdown('<div class="search-wrap"><div class="search-label">🔎 Search Query</div>', unsafe_allow_html=True)
    query = st.text_input(
        label="query_input",
        placeholder='e.g.  "Goldman Sachs interest rate swap USD SOFR 5 year"',
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Filters row
    st.markdown('<div class="filter-section"><div class="filter-title">⚙ Filters</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    with c1:
        trade_type = st.selectbox("Trade Type", trade_types, key="f_trade")
    with c2:
        jurisdiction = st.selectbox("Jurisdiction", jurisdictions, key="f_jur")
    with c3:
        product = st.selectbox("Product", products, key="f_prod")
    with c4:
        top_k = st.number_input("Results", min_value=1, max_value=20, value=5, key="f_topk")
    st.markdown('</div>', unsafe_allow_html=True)

    # Search button
    col_btn, col_opt = st.columns([2, 8])
    with col_btn:
        search_clicked = st.button("⚡  Search", use_container_width=True)
    with col_opt:
        active_only = st.checkbox("Active templates only", value=True)

    # Run search
    if search_clicked or (query and st.session_state.get("last_query") != query):
        if not query.strip():
            st.markdown('<div class="alert alert-warn">⚠ Please enter a search query.</div>', unsafe_allow_html=True)
            return

        st.session_state.last_query = query

        payload = {
            "query": query,
            "top_k": top_k,
            "active_only": active_only,
        }
        if trade_type != "All":   payload["trade_type"]  = trade_type
        if jurisdiction != "All": payload["jurisdiction"] = jurisdiction
        if product != "All":      payload["product"]      = product

        with st.spinner(""):
            start = time.time()
            result = api_post("/search", payload)
            elapsed = round((time.time() - start) * 1000)

        if not result or "error" in result:
            st.markdown(f'<div class="alert alert-error">❌ Search failed. Is the API running at {API_BASE}?</div>', unsafe_allow_html=True)
            return

        total = result.get("total_results", 0)
        search_ms = result.get("search_time_ms", elapsed)
        filters_applied = result.get("filters_applied", {})

        # Results header
        filter_str = "  ·  ".join([f"{k}: <b>{v}</b>" for k, v in filters_applied.items()]) if filters_applied else "no filters"
        st.markdown(f"""<div style="display:flex; align-items:center; justify-content:space-between;
            margin: 8px 0 20px; padding: 14px 18px;
            background: rgba(0,212,255,0.05);
            border: 1px solid rgba(0,212,255,0.15);
            border-radius: 10px;">
    <div style="font-size:13px; color:rgba(255,255,255,0.6);">
        Found <span style="color:#00d4ff; font-weight:700; font-size:16px;">{total}</span>
        result{"s" if total != 1 else ""} &nbsp;·&nbsp; {filter_str}
    </div>
    <div style="font-size:11px; color:rgba(255,255,255,0.25);">
        ⏱ {search_ms}ms
    </div>
</div>""", unsafe_allow_html=True)

        if total == 0:
            st.markdown('<div class="alert alert-info">💡 No templates matched. Try broader search terms or remove filters.</div>', unsafe_allow_html=True)
            return

        # Result cards
        for i, r in enumerate(result["results"]):
            score = r["score"]
            bar_width = int(score * 100)
            bar_color = score_color(score)
            cp_short = r["counterparty"].split(" and ")[0] if " and " in r["counterparty"] else r["counterparty"]
            cp_short = cp_short[:35] + "…" if len(cp_short) > 35 else cp_short

            # Strip any HTML tags from the snippet so raw HTML never renders in the card
            import re as _re, html as _html
            raw_snippet = r.get("snippet", "")
            clean_snippet = _re.sub(r"<[^>]+>", " ", raw_snippet)   # strip tags
            clean_snippet = _html.escape(clean_snippet)              # escape entities
            clean_snippet = " ".join(clean_snippet.split())          # collapse whitespace
            clean_snippet = clean_snippet[:220] + "…" if len(clean_snippet) > 220 else clean_snippet

            _card = (
                f'<div class="result-card">'
                f'<div class="rank-badge">#{i+1}</div>'
                f'<div class="result-filename">📄 {_html.escape(r["filename"])}</div>'
                f'<div class="score-wrap">'
                f'<div class="score-label"><span>RELEVANCE SCORE</span>'
                f'<span style="color:#fff;font-weight:700;">{score:.3f}</span></div>'
                f'<div class="score-bar-bg">'
                f'<div class="score-bar-fill" style="width:{bar_width}%;background:{bar_color};"></div>'
                f'</div></div>'
                f'<div class="result-snippet">{clean_snippet}</div>'
                f'<div class="badge-row">'
                f'<span class="badge badge-trade">⚡ {_html.escape(r["trade_type"])}</span> '
                f'<span class="badge badge-cp">🏦 {_html.escape(cp_short)}</span> '
                f'<span class="badge badge-jur">🌍 {_html.escape(r["jurisdiction"])}</span> '
                f'<span class="badge badge-prod">📦 {_html.escape(r["product"])}</span> '
                f'<span class="badge badge-ver">v{_html.escape(str(r["version"]))}</span> '
                f'{status_badge(r["status"])}'
                f'</div></div>'
            )
            st.markdown(_card, unsafe_allow_html=True)

            with st.expander(f"⬇ Download  ·  {r['filename']}"):
                st.markdown(f"""<div style="display:flex; gap:12px; align-items:center; padding:8px 0;">
    <a href="{API_BASE}/templates/{r['doc_id']}/download"
       target="_blank"
       style="display:inline-flex; align-items:center; gap:8px;
              padding:9px 20px; border-radius:8px;
              background:linear-gradient(135deg,#00d4ff,#00a8cc);
              color:#000; font-weight:700; font-size:13px;
              text-decoration:none; font-family:'Syne',sans-serif;">
        ⬇ Download .docx
    </a>
    <span style="font-size:12px; color:rgba(255,255,255,0.3);">
        doc_id: {r['doc_id'][:20]}…
    </span>
</div>""", unsafe_allow_html=True)


# ─── Page: Template Browser ───────────────────────────────────────────────

def page_browser():
    st.markdown("""<div class="page-header">
    <div class="page-title">Template <span>Browser</span></div>
    <div class="page-subtitle">Browse and manage all templates in the repository</div>
</div>""", unsafe_allow_html=True)

    facets = api_get("/facets") or {}

    # Filter bar
    c1, c2, c3 = st.columns(3)
    with c1:
        f_trade = st.selectbox("Trade Type", ["All"] + facets.get("trade_types", []), key="b_trade")
    with c2:
        f_jur = st.selectbox("Jurisdiction", ["All"] + facets.get("jurisdictions", []), key="b_jur")
    with c3:
        f_prod = st.selectbox("Product", ["All"] + facets.get("products", []), key="b_prod")

    show_all = st.checkbox("Include draft & deprecated", value=False)

    # Build query
    params = f"?active_only={str(not show_all).lower()}"
    if f_trade != "All": params += f"&trade_type={f_trade}"
    if f_jur   != "All": params += f"&jurisdiction={f_jur}"
    if f_prod  != "All": params += f"&product={f_prod}"

    data = api_get(f"/templates{params}")
    if not data:
        st.markdown(f'<div class="alert alert-error">❌ Cannot reach API at {API_BASE}</div>', unsafe_allow_html=True)
        return

    templates = data.get("templates", [])
    total = data.get("total", 0)

    # Metrics
    active_count = sum(1 for t in templates if t.get("status") == "active")
    draft_count  = sum(1 for t in templates if t.get("status") == "draft")
    trade_count  = len(set(t.get("trade_type") for t in templates))

    _mc = '<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px;">'
    _mc += f'<div style="flex:1;min-width:130px;padding:18px 16px;border-radius:14px;text-align:center;background:rgba(0,212,255,0.12);border:1px solid rgba(0,212,255,0.3);"><div style="font-size:22px;margin-bottom:6px;">📋</div><div style="font-family:Inter,sans-serif;font-size:28px;font-weight:900;color:#00D4FF;line-height:1;">{total}</div><div style="font-size:11px;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Total Templates</div></div>'
    _mc += f'<div style="flex:1;min-width:130px;padding:18px 16px;border-radius:14px;text-align:center;background:rgba(0,255,136,0.12);border:1px solid rgba(0,255,136,0.3);"><div style="font-size:22px;margin-bottom:6px;">✅</div><div style="font-family:Inter,sans-serif;font-size:28px;font-weight:900;color:#00FF88;line-height:1;">{active_count}</div><div style="font-size:11px;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Active</div></div>'
    _mc += f'<div style="flex:1;min-width:130px;padding:18px 16px;border-radius:14px;text-align:center;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);"><div style="font-size:22px;margin-bottom:6px;">📝</div><div style="font-family:Inter,sans-serif;font-size:28px;font-weight:900;color:#F59E0B;line-height:1;">{draft_count}</div><div style="font-size:11px;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Draft</div></div>'
    _mc += f'<div style="flex:1;min-width:130px;padding:18px 16px;border-radius:14px;text-align:center;background:rgba(168,85,247,0.12);border:1px solid rgba(168,85,247,0.3);"><div style="font-size:22px;margin-bottom:6px;">⚡</div><div style="font-family:Inter,sans-serif;font-size:28px;font-weight:900;color:#A855F7;line-height:1;">{trade_count}</div><div style="font-size:11px;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Trade Types</div></div>'
    _mc += '</div>'
    st.markdown(_mc, unsafe_allow_html=True)

    if not templates:
        st.markdown('<div class="alert alert-info">No templates found with current filters.</div>', unsafe_allow_html=True)
        return

    # Table — build flat single-line HTML (no leading whitespace/newlines that Streamlit treats as code blocks)
    import html as _html
    rows = ""
    for t in templates:
        cp_short = t["counterparty"].split(" and ")[0] if " and " in t["counterparty"] else t["counterparty"]
        cp_short = cp_short[:30] + "…" if len(cp_short) > 30 else cp_short
        rows += (
            f'<tr>'
            f'<td><span class="tmpl-filename">{_html.escape(t["filename"])}</span></td>'
            f'<td><span class="badge badge-trade">⚡ {_html.escape(t["trade_type"])}</span></td>'
            f'<td style="color:rgba(255,255,255,0.6);">{_html.escape(cp_short)}</td>'
            f'<td><span class="badge badge-jur">🌍 {_html.escape(t["jurisdiction"])}</span></td>'
            f'<td><span class="badge badge-prod">📦 {_html.escape(t["product"])}</span></td>'
            f'<td><span class="badge badge-ver">v{_html.escape(str(t["version"]))}</span></td>'
            f'<td>{status_badge(t["status"])}</td>'
            f'<td><a href="{API_BASE}/templates/{t["doc_id"]}/download" target="_blank" '
            f'style="color:#00d4ff;font-size:12px;text-decoration:none;font-weight:600;">⬇ .docx</a></td>'
            f'</tr>'
        )

    table_html = (
        '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
        'border-radius:14px;overflow:hidden;overflow-x:auto;">'
        '<table class="tmpl-table">'
        '<thead><tr>'
        '<th>Filename</th><th>Trade Type</th><th>Counterparty</th>'
        '<th>Jurisdiction</th><th>Product</th><th>Version</th>'
        '<th>Status</th><th>Download</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)


# ─── Page: Upload ─────────────────────────────────────────────────────────

def page_upload():
    st.markdown("""<div class="page-header">
    <div class="page-title">Upload <span>New Template</span></div>
    <div class="page-subtitle">Add a new trade confirmation template to the repository</div>
</div>""", unsafe_allow_html=True)

    st.markdown("""<div class="upload-zone">
    <div class="upload-icon">📄</div>
    <div class="upload-title">Drop your template file below</div>
    <div class="upload-sub">Supported formats: .docx · .pdf · .txt &nbsp;·&nbsp; Max size: 50MB</div>
</div>""", unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Choose a template file",
        type=["docx", "pdf", "txt"],
        label_visibility="collapsed",
    )

    force = st.checkbox("Force re-ingest if file already exists", value=False)

    if uploaded:
        st.markdown(f"""<div class="alert alert-info">
    📎 Ready to ingest: <b>{uploaded.name}</b>
    ({round(len(uploaded.getvalue()) / 1024, 1)} KB)
</div>""", unsafe_allow_html=True)

        if st.button("⬆  Ingest Template", use_container_width=False):
            with st.spinner("Parsing, embedding and storing..."):
                try:
                    files = {"file": (uploaded.name, uploaded.getvalue(),
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                    data  = {"force": str(force).lower()}
                    r = requests.post(f"{API_BASE}/ingest/file", files=files, data=data, timeout=30)
                    result = r.json()
                except Exception as e:
                    result = {"error": str(e)}

            if "error" in result and not result.get("success"):
                st.markdown(f'<div class="alert alert-error">❌ {result.get("error", "Unknown error")}</div>', unsafe_allow_html=True)
            elif result.get("skipped"):
                st.markdown(f'<div class="alert alert-warn">⏭ {result["message"]} Use force re-ingest to overwrite.</div>', unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="alert alert-success">
    ✅ <b>{result.get('filename')}</b> ingested successfully!<br>
    <span style="font-size:11px; opacity:0.7;">
        Trade Type: {result.get('trade_type', 'N/A')} &nbsp;·&nbsp;
        doc_id: {result.get('doc_id', 'N/A')[:24]}…
    </span>
</div>""", unsafe_allow_html=True)
                api_get.clear()

    # Guidelines
    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
    st.markdown("""<div style="font-family:'Syne',sans-serif; font-size:13px; font-weight:700;
            color:rgba(255,255,255,0.5); letter-spacing:1px; text-transform:uppercase;
            margin-bottom:14px;">
    📋 Template Guidelines
</div>""", unsafe_allow_html=True)

    cols = st.columns(2)
    guidelines = [
        ("✅ Include trade type in the title",         "badge-active"),
        ("✅ Add counterparty and jurisdiction fields", "badge-active"),
        ("✅ Use structured Economic Terms section",    "badge-active"),
        ("✅ Include ISDA Agreement reference",         "badge-active"),
        ("⚠ Avoid scanned PDFs (OCR not supported)",  "badge-draft"),
        ("⚠ Keep file size under 50MB",               "badge-draft"),
    ]
    for i, (text, cls) in enumerate(guidelines):
        with cols[i % 2]:
            st.markdown(f'<div class="badge {cls}" style="margin:4px 0; display:block; border-radius:8px;">{text}</div>', unsafe_allow_html=True)


# ─── Page: Admin ──────────────────────────────────────────────────────────

def page_admin():
    st.markdown("""<div class="page-header">
    <div class="page-title">Admin <span>Panel</span></div>
    <div class="page-subtitle">Manage the template repository and system settings</div>
</div>""", unsafe_allow_html=True)

    # Health card
    online, health = check_api()
    if online:
        ts = health.get("timestamp", "")[:19].replace("T", " ")
        st.markdown(f"""<div style="background:rgba(0,255,136,0.05); border:1px solid rgba(0,255,136,0.15);
            border-radius:14px; padding:22px; margin-bottom:24px;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <div style="font-family:'Syne',sans-serif; font-size:16px; font-weight:700; color:#00ff88;">
                ● API Healthy
            </div>
            <div style="font-size:12px; color:rgba(255,255,255,0.35); margin-top:4px;">
                {health.get('templates_in_store',0)} templates &nbsp;·&nbsp;
                {health.get('embedding_backend','')} &nbsp;·&nbsp;
                Store: {health.get('vector_store_backend','')} &nbsp;·&nbsp;
                {ts} UTC
            </div>
        </div>
        <div style="font-size:32px; opacity:0.3;">⚙️</div>
    </div>
</div>""", unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alert alert-error">❌ API offline — start with: uvicorn src.api.main:app --port 8000</div>', unsafe_allow_html=True)

    # Refresh all
    st.markdown("""<div style="font-family:'Syne',sans-serif; font-size:13px; font-weight:700;
            color:rgba(255,255,255,0.4); letter-spacing:1px; text-transform:uppercase;
            margin-bottom:12px;">🔄 Re-Ingest All Templates</div>""", unsafe_allow_html=True)

    c1, c2 = st.columns([3, 7])
    with c1:
        force_refresh = st.checkbox("Force re-embed all", value=False)
    with c2:
        if st.button("🔄  Refresh Repository", use_container_width=False):
            with st.spinner("Re-ingesting all templates..."):
                r = requests.post(f"{API_BASE}/ingest/refresh?force={str(force_refresh).lower()}", timeout=60)
                result = r.json() if r.status_code == 200 else {"error": r.text}

            if "error" in result:
                st.markdown(f'<div class="alert alert-error">❌ {result["error"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="alert alert-success">
    ✅ Refresh complete — ingested: {result['ingested']},
    skipped: {result['skipped']}, failed: {result['failed']},
    duration: {result['duration_seconds']}s
</div>""", unsafe_allow_html=True)
                api_get.clear()

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # Delete templates
    st.markdown("""<div style="font-family:'Syne',sans-serif; font-size:13px; font-weight:700;
            color:rgba(255,255,255,0.4); letter-spacing:1px; text-transform:uppercase;
            margin-bottom:12px;">🗑 Remove Template from Store</div>""", unsafe_allow_html=True)

    data = api_get("/templates?active_only=false")
    if data and data.get("templates"):
        templates = data["templates"]
        options = {f"{t['filename']}  [{t['status']}]": t["doc_id"] for t in templates}
        selected = st.selectbox("Select template to remove", list(options.keys()))
        doc_id = options.get(selected, "")

        st.markdown('<div class="alert alert-warn">⚠ This removes the template from the vector store. The source .docx file is preserved on disk.</div>', unsafe_allow_html=True)

        if st.button("🗑  Remove Selected Template"):
            result = api_delete(f"/templates/{doc_id}")
            if result and result.get("deleted"):
                st.markdown(f'<div class="alert alert-success">✅ Removed: {result["filename"]}</div>', unsafe_allow_html=True)
                api_get.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.markdown(f'<div class="alert alert-error">❌ Delete failed: {result}</div>', unsafe_allow_html=True)


# ─── JS Animation Injector ────────────────────────────────────────────────
# Injects page-transition and 3D tilt effects via vanilla JS

ANIMATION_JS = """<script>
(function(){
  'use strict';

  /* ── Page fade-in ─────────────────────────────── */
  var root = document.documentElement;
  root.style.cssText += 'opacity:0;transition:opacity .32s ease';
  requestAnimationFrame(function(){
    requestAnimationFrame(function(){ root.style.opacity='1'; });
  });

  /* ── 3D mouse-tilt ────────────────────────────── */
  function tilt(sel, depth){
    document.querySelectorAll(sel).forEach(function(el){
      el.addEventListener('mousemove', function(e){
        var r=el.getBoundingClientRect(),
            x=(e.clientX-r.left)/r.width-.5,
            y=(e.clientY-r.top)/r.height-.5;
        el.style.transform='perspective(600px) rotateY('+x*depth+'deg) rotateX('+(-y*depth)+'deg) translateY(-4px) scale(1.012)';
        el.style.transition='transform .1s ease';
      });
      el.addEventListener('mouseleave', function(){
        el.style.transform='';
        el.style.transition='transform .45s cubic-bezier(.34,1.56,.64,1)';
      });
    });
  }

  /* ── Scroll reveal ────────────────────────────── */
  function reveal(){
    if(!('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(e.isIntersecting){
          e.target.style.opacity='1';
          e.target.style.transform='none';
          io.unobserve(e.target);
        }
      });
    },{threshold:.08,rootMargin:'0px 0px -20px 0px'});

    document.querySelectorAll('.result-card,.disc-card,.metric-card,[data-testid="stExpander"]').forEach(function(el){
      if(getComputedStyle(el).opacity==='1'){
        el.style.opacity='0';
        el.style.transform='translateY(18px) scale(.98)';
        el.style.transition='opacity .38s ease,transform .38s cubic-bezier(.22,1,.36,1)';
        io.observe(el);
      }
    });
  }

  /* ── Animated score bars ──────────────────────── */
  function animateBars(){
    document.querySelectorAll('.score-bar-fill').forEach(function(el){
      var w = el.style.width || el.getAttribute('data-width');
      if(w && !el.dataset.animated){
        el.dataset.animated='1';
        el.style.setProperty('--w', w);
        el.style.width='0';
        el.style.animation='barFill 1s cubic-bezier(.4,0,.2,1) .2s both';
      }
    });
  }

  /* ── Nav active glow ──────────────────────────── */
  function navGlow(){
    document.querySelectorAll('[data-testid="stSidebar"] button').forEach(function(btn){
      btn.addEventListener('click', function(){
        document.querySelectorAll('[data-testid="stSidebar"] button').forEach(function(b){
          b.style.borderLeft='';b.style.background='';
        });
        btn.style.borderLeft='3px solid #00d4ff';
        btn.style.background='rgba(0,212,255,.12)';
      });
    });
  }

  /* ── Particle cursor trail ────────────────────── */
  var trail=[];
  document.addEventListener('mousemove',function(e){
    var p=document.createElement('div');
    p.style.cssText='position:fixed;pointer-events:none;z-index:9999;width:5px;height:5px;border-radius:50%;background:rgba(0,212,255,.55);left:'+(e.clientX-2)+'px;top:'+(e.clientY-2)+'px;transform:scale(1);transition:transform .6s ease,opacity .6s ease;';
    document.body.appendChild(p);
    trail.push(p);
    if(trail.length>18) document.body.removeChild(trail.shift());
    requestAnimationFrame(function(){p.style.transform='scale(0)';p.style.opacity='0';});
    setTimeout(function(){if(p.parentNode)p.parentNode.removeChild(p);},620);
  });

  /* ── Page transition flash ────────────────────── */
  function pageFlash(){
    var flash=document.createElement('div');
    flash.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:9998;background:linear-gradient(135deg,rgba(0,212,255,.04),rgba(0,255,136,.03));animation:fadeIn .35s ease both;';
    document.body.appendChild(flash);
    setTimeout(function(){if(flash.parentNode)flash.parentNode.removeChild(flash);},400);
  }

  /* ── Apply all after each Streamlit render ──────── */
  var _applied = 0;
  function apply(){
    var now = Date.now();
    if(now - _applied < 150) return;
    _applied = now;
    tilt('.result-card', 9);
    tilt('.metric-card', 6);
    tilt('.disc-card', 5);
    tilt('.auth-card', 4);
    reveal();
    animateBars();
    navGlow();
  }

  /* Watch Streamlit re-renders */
  new MutationObserver(function(muts){
    var hasNew = muts.some(function(m){ return m.addedNodes.length>0; });
    if(hasNew){ pageFlash(); setTimeout(apply,200); }
  }).observe(document.body,{childList:true,subtree:true});

  setTimeout(apply, 400);
})();
</script>"""

def inject_animations():
    st.markdown(ANIMATION_JS, unsafe_allow_html=True)


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    init_session()
    _inject_css()           # load CSS once — skipped if already injected
    inject_animations()     # 3D tilt + scroll reveal + cursor trail

    # ── Auth gate ─────────────────────────────────────────────────────────
    if not is_authenticated():
        render_auth_page()
        return

    # ── Authenticated — render app ────────────────────────────────────────
    page = render_sidebar()

    # ── Guard: redirect if user navigated to a page they can't access ────
    _page_permission_map = {
        "search":     "search",
        "recommender":"recommender",
        "generate":   "generate",
        "bulk":       "generate",
        "email":      "generate",
        "diff":       "diff",
        "sidebyside": "sidebyside",
        "heatmap":    "heatmap",
        "versions":   "versions",
        "clauses":    "clauses",
        "upload":     "upload",
        "audit":      "audit",
        "admin":      "admin",
        "browser":    None,   # always allowed
    }
    #role = st.session_state.get("role", None)
    # bulk and email not available to user role even though generate is
    #if page in ("bulk", "email") and role == "user":
     #   st.session_state.page = "generate"
      #  st.rerun()
    required_perm = _page_permission_map.get(page)
    role = st.session_state.get("role", None)
    if required_perm and not can_access(role, required_perm):
        st.session_state.page = "search"
        st.warning("You don't have access to that page.")
        st.rerun()

    with st.container():
        if page == "search":
            page_search()
            return
        elif page == "browser":
            page_browser()
            return
        elif page == "upload":
            page_upload()
            return
        elif page == "admin":
            page_admin()
            return
        elif page == "diff":
            page_diff()
            return
        elif page == "generate":
            page_generate()
            return
        elif page == "bulk":
            page_bulk()
            return
        elif page == "audit":
            page_audit()
            return
        elif page == "sidebyside":
            page_sidebyside()
            return
        elif page == "heatmap":
            page_heatmap()
            return
        elif page == "versions":
            page_versions()
            return
        elif page == "recommender":
            page_recommender()
            return
        elif page == "clauses":
            page_clause_editor()
            return
        elif page == "email":
            page_email()
            return


if __name__ == "__main__":
    main()
