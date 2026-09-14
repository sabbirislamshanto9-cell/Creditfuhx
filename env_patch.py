"""env_patch.py - Railway environment ভ্যারিয়েবল দিয়ে panel login override করার মিনিমাল প্যাচ।
Railway এ Variables ট্যাবে PANEL_SECRET ও PANEL_USER_PASS বসালেই লগিন পাসওয়ার্ড বদলে যায়।
Default (FSFUHX / FXFUHXFFKING) আগের মতোই কাজ করে।
ব্যবহার: app.py এ `import env_patch` যোগ করুন (import ব্লকের নিচে)।
"""
import os
import hashlib

try:
    from app import CONFIG, DEFAULT_USERS
except Exception:
    CONFIG = {}
    DEFAULT_USERS = {}

secret_env = (os.environ.get('PANEL_SECRET') or '').strip()
userpass_env = (os.environ.get('PANEL_USER_PASS') or '').strip()

if secret_env and 'passwords' in CONFIG:
    CONFIG['passwords']['secret'] = hashlib.sha256(secret_env.encode()).hexdigest()

if userpass_env and 'passwords' in CONFIG:
    CONFIG['passwords']['user'] = hashlib.sha256(userpass_env.encode()).hexdigest()

if secret_env:
    for uid, u in DEFAULT_USERS.items():
        u['password_hash'] = hashlib.sha256(secret_env.encode()).hexdigest()
