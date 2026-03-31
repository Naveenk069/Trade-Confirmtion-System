"""
auth.py — Authentication & Authorization module.

JWT token generation and verification using stdlib only (hmac + hashlib).
Password hashing using hashlib pbkdf2_hmac (bcrypt-equivalent security).
User store as JSON file (upgradeable to SQLite / PostgreSQL).

Roles:
    analyst  — Search, View, Generate (read + generate)
    manager  — Analyst + Diff, Download reports
    admin    — Full access including Upload, Delete, Admin panel
"""

import json
import hmac
import hashlib
import base64
import time
import os
import re
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────
SECRET_KEY    = os.environ.get("JWT_SECRET", "tradeconfirm-ai-secret-key-2026-change-in-prod")
TOKEN_EXPIRY  = 8 * 3600        # 8 hours
USERS_FILE    = Path(__file__).parent.parent / "data" / "users.json"
AUDIT_FILE    = Path(__file__).parent.parent / "data" / "audit_log.json"

ROLE_PERMISSIONS = {
    "user":    ["browser"],
    "analyst": ["search", "browser", "generate"],
    "manager": ["search", "browser", "generate", "diff", "download"],
    "admin":   ["search", "browser", "generate", "diff", "download", "upload", "admin"],
}

# ── User Store ────────────────────────────────────────────────────────────
def _load_users() -> dict:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        # Seed default admin user
        default = {
            "admin": {
                "username": "admin",
                "password_hash": _hash_password("admin123"),
                "role": "admin",
                "full_name": "System Administrator",
                "email": "admin@tradeconfirm.ai",
                "created_at": time.time(),
                "last_login": None,
            }
        }
        _save_users(default)
        return default
    with open(USERS_FILE) as f:
        return json.load(f)

def _save_users(users: dict):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ── Password Hashing (PBKDF2-HMAC-SHA256) ────────────────────────────────
def _hash_password(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = base64.b64encode(os.urandom(16)).decode()
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 260000
    )
    return f"{salt}${base64.b64encode(key).decode()}"

def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, _ = stored_hash.split("$", 1)
        return hmac.compare_digest(stored_hash, _hash_password(password, salt))
    except Exception:
        return False

# ── JWT (HS256 using stdlib hmac) ─────────────────────────────────────────
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (pad % 4))

def create_token(username: str, role: str) -> str:
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "sub": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY,
    }).encode())
    sig = _b64url(hmac.new(
        SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest())
    return f"{header}.{payload}.{sig}"

def verify_token(token: str) -> Optional[dict]:
    try:
        header, payload, sig = token.split(".")
        expected = _b64url(hmac.new(
            SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64url_decode(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None

# ── Auth Actions ──────────────────────────────────────────────────────────
def login(username: str, password: str) -> tuple[bool, str, Optional[dict]]:
    """Returns (success, message, user_dict)."""
    users = _load_users()
    u = users.get(username.lower().strip())
    if not u:
        return False, "Invalid username or password.", None
    if not _verify_password(password, u["password_hash"]):
        return False, "Invalid username or password.", None
    # Update last login
    u["last_login"] = time.time()
    users[username.lower().strip()] = u
    _save_users(users)
    token = create_token(u["username"], u["role"])
    log_audit(username, "LOGIN", "Authentication successful")
    return True, token, u

def signup(username: str, password: str, full_name: str,
           email: str, role: str = "analyst") -> tuple[bool, str]:
    """Returns (success, message)."""
    username = username.lower().strip()
    if not re.match(r"^[a-z0-9_]{3,20}$", username):
        return False, "Username must be 3–20 characters: letters, numbers, underscore only."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False, "Please enter a valid email address."
    if role not in ROLE_PERMISSIONS:
        return False, f"Invalid role. Choose from: {', '.join(ROLE_PERMISSIONS.keys())}"
    users = _load_users()
    if username in users:
        return False, "Username already exists. Please choose another."
    users[username] = {
        "username": username,
        "password_hash": _hash_password(password),
        "role": role,
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "created_at": time.time(),
        "last_login": None,
    }
    _save_users(users)
    log_audit(username, "SIGNUP", f"New account created — role: {role}")
    return True, "Account created successfully. You can now log in."

def get_user(username: str) -> Optional[dict]:
    return _load_users().get(username.lower().strip())

def can_access(role: str, feature: str) -> bool:
    return feature in ROLE_PERMISSIONS.get(role, [])

def list_users() -> list:
    users = _load_users()
    return [
        {k: v for k, v in u.items() if k != "password_hash"}
        for u in users.values()
    ]

def delete_user(username: str) -> bool:
    users = _load_users()
    if username not in users or username == "admin":
        return False
    del users[username]
    _save_users(users)
    return True

def change_role(username: str, new_role: str) -> bool:
    users = _load_users()
    if username not in users or new_role not in ROLE_PERMISSIONS:
        return False
    users[username]["role"] = new_role
    _save_users(users)
    return True

# ── Audit Logging ─────────────────────────────────────────────────────────
def log_audit(username: str, action: str, detail: str = ""):
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    logs = []
    if AUDIT_FILE.exists():
        try:
            with open(AUDIT_FILE) as f:
                logs = json.load(f)
        except Exception:
            logs = []
    logs.append({
        "timestamp": time.time(),
        "datetime":  time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "username":  username,
        "action":    action,
        "detail":    detail,
    })
    # Keep last 1000 entries
    logs = logs[-1000:]
    with open(AUDIT_FILE, "w") as f:
        json.dump(logs, f, indent=2)

def get_audit_logs(limit: int = 100) -> list:
    if not AUDIT_FILE.exists():
        return []
    try:
        with open(AUDIT_FILE) as f:
            logs = json.load(f)
        return list(reversed(logs[-limit:]))
    except Exception:
        return []
