#!/usr/bin/env python3
"""
FX HOSTING - Ultimate VPS Management Panel
Version: 4.0.0 - ADMIN MODE (single-role system)
"""

import os, sys, signal, subprocess, threading, time, shutil, zipfile, py7zr
import psutil, json, hashlib, secrets, re, platform, socket, datetime, base64, math
import requests
from flask import Flask, render_template, render_template_string, request, jsonify, redirect, url_for, send_file, session, abort, Response, make_response
from functools import wraps
from pathlib import Path

# Railway env vars (PANEL_SECRET / PANEL_USER_PASS) login override - optional
# (env_patch মার্জ করে app.py তেই রাখা হয়েছে)
def _apply_env_login_overrides():
    _secret_env = (os.environ.get('PANEL_SECRET') or '').strip()
    _userpass_env = (os.environ.get('PANEL_USER_PASS') or '').strip()
    if not _secret_env and not _userpass_env:
        return
    if _secret_env and 'passwords' in CONFIG:
        CONFIG['passwords']['secret'] = hashlib.sha256(_secret_env.encode()).hexdigest()
    if _userpass_env and 'passwords' in CONFIG:
        CONFIG['passwords']['user'] = hashlib.sha256(_userpass_env.encode()).hexdigest()
    if _secret_env:
        for _uid, _u in DEFAULT_USERS.items():
            _u['password_hash'] = hashlib.sha256(_secret_env.encode()).hexdigest()



app = Flask(__name__)

# Secret key persistence
SECRET_KEY_FILE = 'secret_key.txt'
if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, 'r') as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    with open(SECRET_KEY_FILE, 'w') as f:
        f.write(app.secret_key)

app.config.update(
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=3650)
)

# =============================================================================
# CONFIGURATION
# =============================================================================
BASE_DIR = os.getcwd()
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'user_files')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
DB_FILE = 'servers_db.json'
CONFIG_FILE = 'config.json'
ACTIVITY_LOG = 'activity_log.json'
START_TIME = time.time()

for folder in [STATIC_FOLDER, UPLOAD_FOLDER, os.path.join(BASE_DIR, 'backups')]:
    os.makedirs(folder, exist_ok=True)

DEFAULT_ICON = "data:image/png;base64,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"

THEMES = {
    "matrix": {"name":"Matrix Green","primary":"#00ff00","secondary":"#00cc00","accent":"#00ff80","bg":"#050505","card_bg":"#0a0f0a","text":"#e0ffe0","danger":"#ff3333","warning":"#ffaa00","info":"#00ccff"},
    "night":  {"name":"Night Blue","primary":"#4d88ff","secondary":"#3366cc","accent":"#aa88ff","bg":"#050510","card_bg":"#0a0a1a","text":"#e0e8ff","danger":"#ff4d4d","warning":"#ffaa00","info":"#00ccff"},
    "ocean":  {"name":"Ocean Blue","primary":"#3399ff","secondary":"#0066cc","accent":"#ff99cc","bg":"#050a15","card_bg":"#0a1525","text":"#e0f0ff","danger":"#ff4d4d","warning":"#ffaa00","info":"#00ccff"},
    "sunset": {"name":"Sunset Orange","primary":"#ff9933","secondary":"#cc6600","accent":"#ff66b3","bg":"#150a05","card_bg":"#1f120a","text":"#fff0e0","danger":"#ff3333","warning":"#ffcc00","info":"#00ccff"},
    "blood":  {"name":"Blood Red","primary":"#ff4d4d","secondary":"#cc0000","accent":"#ff80bf","bg":"#150505","card_bg":"#1f0a0a","text":"#ffe0e0","danger":"#ff0000","warning":"#ffaa00","info":"#00ccff"},
    "neon":   {"name":"Neon Purple","primary":"#cc66ff","secondary":"#9933cc","accent":"#ffff80","bg":"#0a0515","card_bg":"#120a1f","text":"#f0e0ff","danger":"#ff4d4d","warning":"#ffaa00","info":"#00ccff"},
    "cyber":  {"name":"Cyber Cyan","primary":"#33ffff","secondary":"#00cccc","accent":"#ff80ff","bg":"#051015","card_bg":"#0a1a1f","text":"#e0ffff","danger":"#ff4d4d","warning":"#ffaa00","info":"#0088ff"},
    "vapor":  {"name":"Vapor Pink","primary":"#ff99cc","secondary":"#cc6699","accent":"#80ffff","bg":"#150510","card_bg":"#1f0a1a","text":"#ffe0f0","danger":"#ff3333","warning":"#ffcc00","info":"#00ccff"},
    "gold":   {"name":"Royal Gold","primary":"#ffcc66","secondary":"#cc9933","accent":"#ffb380","bg":"#151005","card_bg":"#1f1a0a","text":"#fff8e0","danger":"#ff3333","warning":"#ffaa00","info":"#00ccff"},
    "tokyo":  {"name":"Tokyo Night","primary":"#7aa2f7","secondary":"#565f89","accent":"#bb9af7","bg":"#06080f","card_bg":"#0d111f","text":"#c0caf5","danger":"#f7768e","warning":"#e0af68","info":"#7dcfff"},
    "dracula":{"name":"Dracula","primary":"#ff79c6","secondary":"#bd93f9","accent":"#8be9fd","bg":"#0d0d14","card_bg":"#161620","text":"#f8f8f2","danger":"#ff5555","warning":"#f1fa8c","info":"#8be9fd"},
    "monokai":{"name":"Monokai","primary":"#a6e22e","secondary":"#f92672","accent":"#66d9ef","bg":"#0d0d0d","card_bg":"#1a1a1a","text":"#f8f8f0","danger":"#f92672","warning":"#e6db74","info":"#66d9ef"},
    "nord":   {"name":"Nord","primary":"#88c0d0","secondary":"#81a1c1","accent":"#b48ead","bg":"#0d1117","card_bg":"#161b22","text":"#d8dee9","danger":"#bf616a","warning":"#ebcb8b","info":"#81a1c1"},
    "midnight":{"name":"Midnight","primary":"#7c4dff","secondary":"#512da8","accent":"#ff6e40","bg":"#080510","card_bg":"#110d1f","text":"#f0ecff","danger":"#ff5252","warning":"#ffd740","info":"#40c4ff"},
    "emerald":{"name":"Emerald","primary":"#00e676","secondary":"#00c853","accent":"#69f0ae","bg":"#05150a","card_bg":"#0a1f12","text":"#e0ffec","danger":"#ff5252","warning":"#ffd740","info":"#40c4ff"},
    "amber":  {"name":"Amber","primary":"#ffab00","secondary":"#ff6d00","accent":"#ffe57f","bg":"#151005","card_bg":"#1f1808","text":"#fff8e0","danger":"#ff5252","warning":"#ffcc00","info":"#00b0ff"},
    "ruby":   {"name":"Ruby","primary":"#ff1744","secondary":"#d50000","accent":"#ff8a80","bg":"#150508","card_bg":"#1f0a0f","text":"#ffe0e8","danger":"#ff5252","warning":"#ffd740","info":"#40c4ff"},
    "sapphire":{"name":"Sapphire","primary":"#2979ff","secondary":"#2962ff","accent":"#82b1ff","bg":"#050a15","card_bg":"#0a1025","text":"#e0ecff","danger":"#ff5252","warning":"#ffd740","info":"#00b0ff"},
    "amethyst":{"name":"Amethyst","primary":"#e040fb","secondary":"#aa00ff","accent":"#ea80fc","bg":"#120515","card_bg":"#1c0a1f","text":"#f8e0ff","danger":"#ff5252","warning":"#ffd740","info":"#00b0ff"},
    "silver": {"name":"Silver Grey","primary":"#b3b3b3","secondary":"#808080","accent":"#cccccc","bg":"#0a0a0a","card_bg":"#151515","text":"#f0f0f0","danger":"#ff4d4d","warning":"#ffaa00","info":"#00ccff"},
    "aurora":{"name":"Aurora Navy","primary":"#38bdf8","secondary":"#6366f1","accent":"#a78bfa","bg":"#121b5c","card_bg":"#1a2578","text":"#dbeafe","danger":"#f87171","warning":"#fbbf24","info":"#7dd3fc"},
    "pearl":{"name":"Pearl Light","primary":"#6366f1","secondary":"#38bdf8","accent":"#f43f5e","bg":"#f4f5f9","card_bg":"#ffffff","text":"#1e2235","danger":"#dc2626","warning":"#d97706","info":"#0284c7"},
    "cloud":{"name":"Cloud Sky","primary":"#0ea5e9","secondary":"#6366f1","accent":"#10b981","bg":"#eff6ff","card_bg":"#ffffff","text":"#16263a","danger":"#dc2626","warning":"#d97706","info":"#0891b2"},
    "rose":{"name":"Rose Quartz","primary":"#e11d48","secondary":"#f97316","accent":"#6366f1","bg":"#fff1f2","card_bg":"#ffffff","text":"#3a1520","danger":"#dc2626","warning":"#d97706","info":"#0891b2"}
}

DEFAULT_CONFIG = {
    "site_title": "1HOSTING | Ultimate VPS Panel",
    "site_header": "1HOSTING",
    "icon_url": DEFAULT_ICON,
    "theme": "pearl",
    "font_family": "code",
    "terminal_height": 300,
    "auto_refresh": True,
    "notifications": True,
    "show_system_stats": True,
    "session_timeout": 60,
    "max_log_lines": 2000,
    # JWT Factory — token-generation API endpoint & key (changeable from Settings).
    # Many token APIs need no key at all — leave jwt_api_key blank if yours doesn't.
    "jwt_api_url": os.environ.get('JWT_API_URL', 'https://fiddu-jwt-olive.vercel.app/token').strip(),
    "jwt_api_key": os.environ.get('JWT_API_KEY', '').strip(),
    "passwords": {
        "secret": hashlib.sha256("FXFUHXFFKING".encode()).hexdigest(),
        "user": hashlib.sha256("admin".encode()).hexdigest()
    },
    # Webhook notifications (Discord / Telegram)
    "webhooks": {
        "discord_url": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "notify_on_crash": True,
        "notify_on_start": False,
        "notify_on_stop": False,
        "notify_on_high_cpu": True,
        "cpu_alert_threshold": 90,
        "ram_alert_threshold": 90
    }
}

USERS_FILE = 'users_db.json'
DOMAINS_FILE = 'domains_db.json'
RESOURCE_HISTORY_FILE = 'resource_history.json'

DEFAULT_USERS = {
    "admin_default": {
        "username": "FSFUHX",
        "password_hash": hashlib.sha256("FXFUHXFFKING".encode()).hexdigest(),
        "role": "admin",
        "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "is_builtin": True
    },
    "user_default": {
        "username": "user",
        "password_hash": hashlib.sha256("admin".encode()).hexdigest(),
        "role": "admin",
        "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "is_builtin": True
    }
}

# =============================================================================
# DATA PERSISTENCE
# =============================================================================

def load_json(filename, default=None):
    if default is None: default = {}
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except: return default
    return default

def save_json(filename, data):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

def load_config():
    config = load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
    if 'passwords' not in config:
        config['passwords'] = DEFAULT_CONFIG['passwords']
    return config

CONFIG = load_config()
SERVERS = {}

# ---- Multi-user store ----
def load_users():
    users = load_json(USERS_FILE, None)
    if users is None:
        users = DEFAULT_USERS.copy()
        save_json(USERS_FILE, users)
    return users

def save_users(users):
    save_json(USERS_FILE, users)

USERS = load_users()

# ---- Domain mapping store ----
def load_domains():
    return load_json(DOMAINS_FILE, {})

def save_domains(domains):
    save_json(DOMAINS_FILE, domains)

DOMAINS = load_domains()

# ---- Resource history (per-server CPU/RAM over time, last 60 points = ~30 min @ 30s) ----
def load_resource_history():
    return load_json(RESOURCE_HISTORY_FILE, {})

def save_resource_history(hist):
    save_json(RESOURCE_HISTORY_FILE, hist)

RESOURCE_HISTORY = load_resource_history()
HEALTH_SCORES = {}   # server_id -> {'score': int, 'crashes_24h': int, 'last_crash': str}
CRASH_LOG = {}        # server_id -> list of crash timestamps (epoch)

def log_activity(action, details="", role="system"):
    logs = load_json(ACTIVITY_LOG, [])
    logs.append({
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "action": action,
        "details": details,
        "role": role
    })
    if len(logs) > 1000:
        logs = logs[-800:]
    save_json(ACTIVITY_LOG, logs)

def save_servers():
    try:
        data = {}
        for sid, s in SERVERS.items():
            data[sid] = {
                'cmd': s.get('cmd', ''),
                'cwd': s.get('cwd', ''),
                'path': s.get('path', ''),
                'auto_restart': s.get('auto_restart', False),
                'restart_interval': s.get('restart_interval', '1h'),
                'status': s.get('status', 'stopped'),
                'last_start_time': s.get('last_start_time', 0),
                'created_at': s.get('created_at', time.strftime('%Y-%m-%d %H:%M:%S')),
                'notes': s.get('notes', ''),
                'group': s.get('group', 'default'),
                'tags': s.get('tags', []),
                'env_vars': s.get('env_vars', {})
            }
        save_json(DB_FILE, data)
    except Exception as e:
        print(f"Error saving servers: {e}")

def load_servers():
    global SERVERS
    saved = load_json(DB_FILE, {})
    for sid, s in saved.items():
        SERVERS[sid] = {
            'process': None, 'cmd': s.get('cmd', ''), 'cwd': s.get('cwd', ''),
            'auto_restart': s.get('auto_restart', False), 'restart_interval': s.get('restart_interval', '1h'),
            'logs': [f">>> Server '{sid}' loaded at {time.strftime('%Y-%m-%d %H:%M:%S')}"],
            'status': 'stopped', 'path': s.get('path', ''), 'last_start_time': 0,
            'created_at': s.get('created_at', time.strftime('%Y-%m-%d %H:%M:%S')),
            'notes': s.get('notes', ''), 'group': s.get('group', 'default'),
            'tags': s.get('tags', []), 'env_vars': s.get('env_vars', {})
        }

load_servers()

# =============================================================================
# DECORATORS & ROLE SYSTEM
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Single-role system: every logged-in session is ADMIN MODE"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ================= TRUSTED DEVICE SECURITY (inject) =================
# -*- coding: utf-8 -*-
"""Trusted Device patch — app.py তে inject করা হবে (inject_premium.py দ্বারা)।
সিস্টেম:
- ফোন যেকোনো একবার password দিয়ে login করে 'Save this device' চেক করলে device (uuid cookie)
  PENDING অবস্থায় save হয়; Admin panel → Devices থেকে APPROVE করলে TRUSTED হয়।
- Trusted device পরবর্তীতে আর কখনো password চায় না (permanent): login পেজে device cookie
  থাকলে সিলেন্টলি session বসিয়ে home এ পাঠায়।
- Admin Devices থেকে যেকোনো device REMOVE করা যায় — remove হলে আবার password দিয়ে login করতে হবে।
- CSRF token শুধু POST request নিরাপত্তার জন্য — device শনাক্তকরণে ব্যবহৃত হয় না।
"""

DEVICES_FILE = 'trusted_devices.json'

def _load_devices():
    global DEVICES, DEVICE_LOCK
    try:
        with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
            DEVICES = json.load(f)
    except Exception:
        DEVICES = {}
    with DEVICE_LOCK:
        _save_devices_locked()

def _save_devices_locked():
    try:
        with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEVICES, f, indent=2)
    except Exception:
        pass

def _save_devices():
    with DEVICE_LOCK:
        _save_devices_locked()

DEVICE_LOCK = threading.Lock()
DEVICES = {}
_load_devices()

# =============================================================================
# IP FIREWALL — ৩ বার ভুল password = ২৪ ঘণ্টা IP ban
# =============================================================================
BANLIST_FILE = 'banlist.json'
MAX_LOGIN_FAILS = 3        # কতবার ভুল করলে ban
BAN_DURATION = 24 * 3600   # ২৪ ঘণ্টা
BAN_LOCK = threading.Lock()
BANLIST = {}

def _load_banlist():
    global BANLIST
    try:
        with open(BANLIST_FILE, 'r', encoding='utf-8') as f:
            BANLIST = json.load(f)
    except Exception:
        BANLIST = {}
    # expired entries পরিষ্কার (শুধু যার ban এখনো active — until > 0)
    now = time.time()
    for ip, b in list(BANLIST.items()):
        if b.get('until', 0) > 0 and b.get('until', 0) <= now:
            del BANLIST[ip]

def _save_banlist():
    try:
        with open(BANLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(BANLIST, f, indent=2)
    except Exception:
        pass

def _get_client_ip():
    # proxy (Railway/Nginx) ব্যবহার হলে forward হেডার মানা
    fwd = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    return fwd or request.remote_addr or 'unknown'

def _current_ban():
    """এই IP এখন ban-এ থাকলে {'ip', 'until', 'in': int} দেয়, নয়তো None।"""
    ip = _get_client_ip()
    with BAN_LOCK:
        _load_banlist()
        b = BANLIST.get(ip)
        if b and b.get('until', 0) > time.time():
            left = int(b['until'] - time.time())
            h, m = left // 3600, (left % 3600) // 60
            return {'ip': ip, 'until': b['until'], 'left': left,
                    'message': f"Your IP is banned until {b.get('banned_at','')} — ২৪ ঘণ্টার জন্য ban (banned: {b.get('attempts',0)} বার ভুল password) — আপনার বাকি সময়: {h} ঘণ্টা {m} মিনিট"}
    return None

def ban_fail_count():
    ip = _get_client_ip()
    with BAN_LOCK:
        return BANLIST.get(ip, {}).get('fails', 0)

def _record_login_fail():
    """একটা ভুল login record করে; ৩টা হলে ২৪ ঘণ্টা ban — ban message বা ফাঁকা string return।"""
    ip = _get_client_ip()
    with BAN_LOCK:
        _load_banlist()
        b = BANLIST.setdefault(ip, {'fails': 0, 'until': 0, 'attempts': 0, 'banned_at': ''})
        if b.get('until', 0) > time.time():
            # ইতোমধ্যে ban-এ — কোনো counter update নয়
            return None
        b['fails'] = b.get('fails', 0) + 1
        b['attempts'] = b.get('attempts', 0) + 1
        if b['fails'] >= MAX_LOGIN_FAILS:
            until = time.time() + BAN_DURATION
            b['until'] = until
            b['banned_at'] = time.strftime('%Y-%m-%d %H:%M', time.localtime())
            _save_banlist()
            return f"IP ব্যান হয়েছে (২৪ ঘণ্টা) — ভুল password {MAX_LOGIN_FAILS} বার। আপনার IP ({ip}) lock করা হয়েছে।"
        _save_banlist()
        return None

def _clear_fail():
    """সফল login হলে fail counter reset"""
    ip = _get_client_ip()
    with BAN_LOCK:
        _load_banlist()
        if ip in BANLIST:
            del BANLIST[ip]
            _save_banlist()

_load_banlist()

@app.route('/api/firewall', methods=['GET', 'POST'])
@admin_required
def firewall_api():
    """Admin: ban list দেখা + অনমানে unban (POST {"ip": "..."})"""
    if request.method == 'POST':
        data = request.get_json(force=True) or {}
        ip = (data.get('ip') or '').strip()
        if ip and ip in BANLIST:
            del BANLIST[ip]
            _save_banlist()
            log_activity("Firewall", f"IP unban: {ip}", "admin")
        return jsonify({'ok': True})
    now = time.time()
    out = []
    for ip, b in BANLIST.items():
        if b.get('until', 0) <= now:
            continue
        left = int(b['until'] - now)
        out.append({'ip': ip, 'until': b.get('banned_at',''), 'left_hours': round(left/3600, 1)})
    return jsonify({'banned': out})

def _device_cookie_id():
    """Client cookie থেকে device id পড়ে (CSRF নয়, শুধু device identifier)।"""
    return request.cookies.get('fx_device_id') or request.form.get('device_id') or ''

def _ua_short():
    ua = (request.headers.get('User-Agent') or '')[:90]
    return ua

def _device_label_from_ua():
    ua = _ua_short().lower()
    if 'android' in ua:
        if 'mobile' in ua: return 'Android Phone'
        return 'Android Tablet'
    if 'iphone' in ua or 'ipad' in ua: return 'iOS Device'
    if 'windows' in ua: return 'Windows PC'
    if 'macintosh' in ua: return 'Mac'
    if 'linux' in ua: return 'Linux'
    return 'Unknown Device'

@app.route('/api/devices')
@admin_required
def list_devices():
    """Trusted/Pending device list (admin)"""
    out = []
    for did, d in DEVICES.items():
        out.append({'id': did, 'label': d.get('label', ''), 'browser': d.get('browser', ''),
                    'first_seen': d.get('first_seen', ''), 'trusted': d.get('trusted', False),
                    'pending': d.get('pending', False), 'trusted_at': d.get('trusted_at', ''),
                    'username': d.get('username', 'unknown')})
    return jsonify({'devices': out, 'trusted_count': _count_trusted(), 'max_trust': MAX_SELF_TRUST})

@app.route('/api/devices/<device_id>/approve', methods=['POST'])
@admin_required
def approve_device(device_id):
    if device_id in DEVICES:
        DEVICES[device_id]['trusted'] = True
        DEVICES[device_id]['pending'] = False
        _save_devices()
        log_activity("Device Approved", f"Device '{device_id[:8]}...' trusted", "admin")
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Device not found'}), 404

@app.route('/api/devices/<device_id>/remove', methods=['POST'])
@admin_required
def remove_device(device_id):
    if device_id in DEVICES:
        label = DEVICES[device_id].get('label', device_id[:10])
        del DEVICES[device_id]
        _save_devices()
        log_activity("Device Removed", f"Device '{label}' removed (must re-login with password)", "admin")
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Device not found'}), 404

@app.route('/_auto_login', methods=['GET', 'POST'])
def auto_login():
    """Trusted device automatic login — কোনো password ছাড়া।
    Client login page জাভাস্ক্রিপ্ট থেকে ফাঁকা iframe/img হিসেবে call করে;
    success হলে session বসে এবং page redirect করে।"""
    did = _device_cookie_id()
    if did and did in DEVICES and DEVICES[did].get('trusted'):
        session['logged_in'] = True
        session['is_admin'] = True
        session['login_time'] = time.time()
        session['username'] = DEVICES[did].get('username', 'user')
        session['device_id'] = did
        session['role_label'] = 'ADMIN'
        return jsonify({'ok': True})
    resp = jsonify({'ok': False})
    return resp

@app.route('/_set_device', methods=['POST'])
def set_device():
    """Login পেজে 'Save this device' চেক করলে device save হয় (pending; admin approve করে)।"""
    did = _device_cookie_id()
    if not did:
        return jsonify({'error': 'no device id'}), 400
    DEVICES[did] = {
        'label': request.form.get('label') or _device_label_from_ua(),
        'browser': _ua_short(),
        'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
        'username': session.get('username') or request.form.get('username', 'unknown'),
        'trusted': False,
        'pending': True,
    }
    _save_devices()
    log_activity("Device Pending", f"New device pending: {DEVICES[did]['label']}", "unknown")
    return jsonify({'status': 'pending'})

# Session permanent করা (permanent login — trusted device জীবনভর মনে রাখে)
app.config['SESSION_COOKIE_NAME'] = 'fx_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=3650)

_orig_login_required = login_required
def _trusted_login_check():
    """login_required দেখার আগে trusted cookie দিয়ে session রিস্টোর।"""
    if 'logged_in' not in session:
        did = _device_cookie_id()
        if did and did in DEVICES and DEVICES[did].get('trusted'):
            session['logged_in'] = True
            session['is_admin'] = True
            session['login_time'] = time.time()
            session['username'] = DEVICES[did].get('username', 'user')
            session['device_id'] = did
            session['role_label'] = 'ADMIN'
            session.permanent = True
            log_activity("Auto Login", f"Trusted device '{DEVICES[did]['label']}' auto-logged in", "admin")
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return None

def new_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        r = _trusted_login_check()
        if r is not None:
            return r
        session.permanent = True
        return f(*args, **kwargs)
    return decorated

login_required = new_login_required

def new_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        r = _trusted_login_check()
        if r is not None:
            return r
        session.permanent = True
        return f(*args, **kwargs)
    return decorated

admin_required = new_admin_required


MAX_SELF_TRUST = 2

def _count_trusted():
    """কতটা device এখন trusted (প্রথম MAX_SELF_TRUST টা ফোন সেল্ফ-অ্যাপ্রুভ)।"""
    return sum(1 for d in DEVICES.values() if d.get('trusted'))

def _mark_device_cookie(trust=False):
    """Login সফল হলে device_id cookie বসায় (client এ fx_device_id কুকি পাঠায়)।
    trust=True হলে: trusted device ২টার কম থাকলে সেই মুহূর্তেই trusted (self-approve),
    নয়তো pending — Admin Devices ট্যাব থেকে Approve করতে হবে।
    পুরো check+mark অপারেশন DEVICE_LOCK-এর ভিতরে — race condition ঠেকাতে।"""
    did = request.cookies.get('fx_device_id')
    if not did:
        did = secrets.token_hex(16)
    with DEVICE_LOCK:
        already = did in DEVICES and DEVICES[did].get('trusted')
        should_trust = trust and not already and _count_trusted() < MAX_SELF_TRUST
        if did in DEVICES:
            DEVICES[did]['username'] = session.get('username', 'unknown')
            DEVICES[did]['browser'] = _ua_short()
            if should_trust:
                DEVICES[did]['trusted'] = True
                DEVICES[did]['pending'] = False
                DEVICES[did]['trusted_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            elif not already:
                DEVICES[did]['pending'] = True
            _save_devices_locked()
        else:
            DEVICES[did] = {
                'label': _device_label_from_ua(),
                'browser': _ua_short(),
                'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
                'username': session.get('username', 'unknown'),
                'trusted': should_trust,
                'pending': not should_trust,
            }
            if should_trust:
                DEVICES[did]['trusted_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            _save_devices_locked()
        return DEVICES[did].get('trusted', False)

def _gate_device_login(want_trust):
    """Runs AFTER password verification but BEFORE a session is granted.
    Enforces the real cap: only MAX_SELF_TRUST devices may ever be logged
    in without Admin approval. A correct password alone is no longer
    enough once those slots are full — the login is blocked and the
    device is recorded as pending until an Admin approves it from the
    Devices panel (or removes it, in which case it must ask again).
    Returns (allowed: bool, block_message: str|None).
    """
    did = _device_cookie_id()
    if not did:
        # no device cookie at all (very old client) — can't gate it, allow
        return True, None
    with DEVICE_LOCK:
        dev = DEVICES.get(did)
        if dev and dev.get('trusted'):
            return True, None
        if _count_trusted() < MAX_SELF_TRUST:
            # a free trusted slot exists — this login may proceed
            # (_mark_device_cookie will self-approve it if want_trust is checked)
            return True, None
        # slots are full and this device isn't already trusted — block it
        label = _device_label_from_ua()
        if did in DEVICES:
            DEVICES[did]['trusted'] = False
            DEVICES[did]['pending'] = True
            DEVICES[did]['browser'] = _ua_short()
        else:
            DEVICES[did] = {
                'label': label,
                'browser': _ua_short(),
                'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
                'username': 'unknown',
                'trusted': False,
                'pending': True,
            }
        _save_devices_locked()
    log_activity("Device Blocked", f"Device '{DEVICES[did]['label']}' — correct password but Trusted slots (%d/%d) full, awaiting admin approval" % (_count_trusted(), MAX_SELF_TRUST), "unknown")
    return False, ('Trusted device slot (%d/%d) ভর্তি — এই ডিভাইসটি Admin Approve না করা পর্যন্ত Login করা যাবে না। '
                    'Admin কে Devices প্যানেল থেকে Approve করতে বলুন, তারপর আবার Login করুন।') % (_count_trusted(), MAX_SELF_TRUST)

def get_current_role():
    return "admin"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_system_stats():
    try:
        cpu = psutil.cpu_percent(interval=0.3)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
        boot_time = psutil.boot_time()
        uptime = int(time.time() - boot_time)
        return {
            'cpu': cpu, 'ram_used': round(ram.used/(1024**3),2), 'ram_total': round(ram.total/(1024**3),2),
            'ram_percent': ram.percent, 'disk_used': round(disk.used/(1024**3),2),
            'disk_total': round(disk.total/(1024**3),2), 'disk_percent': round(disk.percent,1),
            'net_sent': round(net.bytes_sent/(1024**2),2), 'net_recv': round(net.bytes_recv/(1024**2),2),
            'load_avg': [round(x,2) for x in load_avg], 'uptime': uptime,
            'processes': len(psutil.pids()), 'connections': len(psutil.net_connections())
        }
    except Exception as e:
        return {'cpu':0,'ram_used':0,'ram_total':0,'ram_percent':0,'disk_used':0,'disk_total':0,'disk_percent':0,'net_sent':0,'net_recv':0,'load_avg':[0,0,0],'uptime':0,'processes':0,'connections':0}

def get_network_info():
    try:
        hostname = socket.gethostname()
        try: ip = socket.gethostbyname(hostname)
        except: ip = "127.0.0.1"
        interfaces = {}
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interfaces[name] = {'ip': addr.address, 'netmask': addr.netmask}
        return {'hostname': hostname, 'ip': ip, 'interfaces': interfaces}
    except:
        return {'hostname':'unknown','ip':'127.0.0.1','interfaces':{}}

PANEL_OWN_PORT = int(os.environ.get('PORT', 5000))

def _proc_connections(p):
    """Compat wrapper: psutil renamed Process.connections() -> Process.net_connections()."""
    try:
        return p.net_connections(kind='inet')
    except AttributeError:
        return p.connections(kind='inet')
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return []

def find_listening_ports(pid):
    """Walk a process and all its children, return every TCP/UDP port it has open in LISTEN state."""
    ports = set()
    try:
        root = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []
    procs = [root]
    try:
        procs += root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    for p in procs:
        try:
            for c in _proc_connections(p):
                if c.status == psutil.CONN_LISTEN and c.laddr:
                    ports.add(c.laddr.port)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return sorted(ports)

# Cache last-known-good port per server so the UI doesn't flicker between polls
_ENDPOINT_CACHE = {}

def get_server_endpoint(server_id):
    """Auto-detect which local port a running server has opened, so it can be
    reached through the panel's built-in reverse proxy at /app/<server_id>/."""
    s = SERVERS.get(server_id)
    if not s or not s.get('process') or s.get('status') != 'running':
        _ENDPOINT_CACHE.pop(server_id, None)
        return {'live': False, 'port': None}
    try:
        pid = s['process'].pid
    except Exception:
        return {'live': False, 'port': None}
    ports = [p for p in find_listening_ports(pid) if p != PANEL_OWN_PORT]
    if ports:
        prev = _ENDPOINT_CACHE.get(server_id)
        port = prev if prev in ports else ports[0]
        _ENDPOINT_CACHE[server_id] = port
        return {'live': True, 'port': port}
    _ENDPOINT_CACHE.pop(server_id, None)
    return {'live': False, 'port': None}

def get_process_resource_usage(pid):
    """CPU% / RAM usage for a server's process tree (used by the overview cards)."""
    try:
        root = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {'cpu': 0, 'mem_mb': 0}
    procs = [root]
    try:
        procs += root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    cpu = 0.0
    mem = 0
    for p in procs:
        try:
            cpu += p.cpu_percent(interval=0.0)
            mem += p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return {'cpu': round(cpu, 2), 'mem_mb': round(mem / (1024 * 1024), 2)}

def format_uptime(seconds):
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)

def kill_process_completely(proc):
    try:
        if proc is None: return
        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)
        for child in children:
            try: child.terminate()
            except: pass
        gone, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            try: child.kill()
            except: pass
        try:
            parent.terminate()
            parent.wait(timeout=3)
        except:
            try: parent.kill()
            except: pass
    except: pass

def log_monitor(server_id, proc_obj):
    server = SERVERS.get(server_id)
    if not server: return
    try:
        for line in iter(proc_obj.stdout.readline, ''):
            if server_id not in SERVERS or SERVERS[server_id].get('process') != proc_obj: break
            if line:
                cleaned = line.strip()
                if cleaned:
                    max_lines = CONFIG.get('max_log_lines', 2000)
                    if len(SERVERS[server_id]['logs']) > max_lines:
                        SERVERS[server_id]['logs'] = SERVERS[server_id]['logs'][-int(max_lines*0.9):]
                    SERVERS[server_id]['logs'].append(cleaned)
    except: pass
    finally:
        try: proc_obj.stdout.close()
        except: pass
    if server_id in SERVERS and SERVERS[server_id].get('process') == proc_obj:
        SERVERS[server_id]['status'] = 'stopped'
        SERVERS[server_id]['process'] = None
        SERVERS[server_id]['logs'].append(">>> [FX HOSTING] Process terminated.")
        save_servers()
        # Crash detection: if it wasn't a manual stop (no explicit 'Stopped'/'restart' log just before)
        recent_logs = SERVERS[server_id]['logs'][-3:]
        was_manual = any('Stopped at' in l or 'restart triggered' in l for l in recent_logs)
        if not was_manual:
            record_crash(server_id)
            notify_event('crash', server_id, "Process exited unexpectedly (possible crash)")

def start_server_internal(server_id, server):
    if server['status'] == 'running': return True
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    for k, v in server.get('env_vars', {}).items():
        env[k] = v
    work_dir = os.path.join(server['path'], server.get('cwd', ''))
    if not os.path.exists(work_dir): work_dir = server['path']
    try:
        if not server['cmd'] or server['cmd'].strip() == '':
            server['logs'].append(">>> [FX HOSTING] Error: No start command specified")
            return False
        if not os.path.exists(work_dir):
            server['logs'].append(f">>> [FX HOSTING] Error: Directory not found: {work_dir}")
            return False
        proc = subprocess.Popen(
            server['cmd'], shell=True, cwd=work_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE, text=True, bufsize=1,
            universal_newlines=True, env=env,
            preexec_fn=os.setsid if os.name != 'nt' else None
        )
        server['process'] = proc
        server['status'] = 'running'
        server['last_start_time'] = time.time()
        server['logs'].append(f">>> [FX HOSTING] Server started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        threading.Thread(target=log_monitor, args=(server_id, proc), daemon=True).start()
        save_servers()
        log_activity("Server Start", f"Server '{server_id}' started", get_current_role())
        notify_event('start', server_id, "Server started successfully")
        return True
    except Exception as e:
        server['logs'].append(f">>> [FX HOSTING] Failed to start: {str(e)}")
        return False

def auto_restarter():
    while True:
        time.sleep(10)
        current_time = time.time()
        for server_id, server in list(SERVERS.items()):
            try:
                if server.get('status') == 'running' and server.get('auto_restart'):
                    interval_map = {'30s':30,'1m':60,'5m':300,'10m':600,'15m':900,'20m':1200,'25m':1500,'30m':1800,'1h':3600,'2h':7200,'3h':10800,'6h':21600,'12h':43200,'24h':86400}
                    interval_sec = interval_map.get(server.get('restart_interval', '1h'), 3600)
                    if current_time - server.get('last_start_time', current_time) >= interval_sec:
                        server['logs'].append(f">>> [FX HOSTING] Auto-restarting...")
                        if server.get('process'): kill_process_completely(server['process'])
                        server['process'] = None
                        server['status'] = 'stopped'
                        start_server_internal(server_id, server)
            except Exception as e:
                print(f"Auto-restart error for {server_id}: {e}")

threading.Thread(target=auto_restarter, daemon=True).start()

# =============================================================================
# WEBHOOK NOTIFICATIONS (Discord / Telegram)
# =============================================================================

def send_discord_webhook(title, description, color=0xff0000):
    url = CONFIG.get('webhooks', {}).get('discord_url', '').strip()
    if not url:
        return
    try:
        import urllib.request
        payload = json.dumps({
            "embeds": [{
                "title": title, "description": description, "color": color,
                "footer": {"text": "FX HOSTING Panel"},
                "timestamp": datetime.datetime.utcnow().isoformat()
            }]
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Discord webhook error: {e}")

def send_telegram_webhook(text):
    wh = CONFIG.get('webhooks', {})
    token = wh.get('telegram_bot_token', '').strip()
    chat_id = wh.get('telegram_chat_id', '').strip()
    if not token or not chat_id:
        return
    try:
        import urllib.request, urllib.parse
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Telegram webhook error: {e}")

def notify_event(event_type, server_id, message):
    """event_type: crash | start | stop | high_cpu | high_ram"""
    wh = CONFIG.get('webhooks', {})
    flag_map = {
        'crash': 'notify_on_crash', 'start': 'notify_on_start',
        'stop': 'notify_on_stop', 'high_cpu': 'notify_on_high_cpu',
        'high_ram': 'notify_on_high_cpu'
    }
    if not wh.get(flag_map.get(event_type, ''), False):
        return
    icons = {'crash': '🔴', 'start': '🟢', 'stop': '🟡', 'high_cpu': '⚠️', 'high_ram': '⚠️'}
    icon = icons.get(event_type, 'ℹ️')
    title = f"{icon} FX HOSTING — {event_type.replace('_',' ').upper()}"
    full_msg = f"{title}\nServer: {server_id}\n{message}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    color_map = {'crash': 0xff0000, 'start': 0x00ff00, 'stop': 0xffaa00, 'high_cpu': 0xff6600, 'high_ram': 0xff6600}
    threading.Thread(target=send_discord_webhook, args=(title, f"**Server:** {server_id}\n{message}", color_map.get(event_type, 0x888888)), daemon=True).start()
    threading.Thread(target=send_telegram_webhook, args=(full_msg,), daemon=True).start()

# =============================================================================
# SERVER HEALTH SCORE & CRASH DETECTION
# =============================================================================

def record_crash(server_id):
    now = time.time()
    CRASH_LOG.setdefault(server_id, [])
    CRASH_LOG[server_id].append(now)
    # keep only last 24h
    CRASH_LOG[server_id] = [t for t in CRASH_LOG[server_id] if now - t < 86400]

def compute_health_score(server_id):
    server = SERVERS.get(server_id)
    if not server:
        return {'score': 0, 'crashes_24h': 0, 'status': 'unknown'}
    crashes_24h = len([t for t in CRASH_LOG.get(server_id, []) if time.time() - t < 86400])
    score = 100
    score -= min(crashes_24h * 15, 60)
    if server.get('status') != 'running':
        score -= 20
    score = max(0, min(100, score))
    if score >= 80: label = 'Excellent'
    elif score >= 60: label = 'Good'
    elif score >= 35: label = 'Degraded'
    else: label = 'Critical'
    return {'score': score, 'crashes_24h': crashes_24h, 'status': label}

def resource_history_collector():
    """Collect per-server CPU/RAM usage (via psutil per-process) every 30s"""
    while True:
        time.sleep(30)
        try:
            for server_id, server in list(SERVERS.items()):
                proc = server.get('process')
                cpu = 0.0
                ram_mb = 0.0
                if proc and server.get('status') == 'running':
                    try:
                        p = psutil.Process(proc.pid)
                        children = p.children(recursive=True)
                        cpu = p.cpu_percent(interval=0.1)
                        ram_mb = p.memory_info().rss / (1024*1024)
                        for c in children:
                            try:
                                cpu += c.cpu_percent(interval=0)
                                ram_mb += c.memory_info().rss / (1024*1024)
                            except: pass
                    except: pass
                RESOURCE_HISTORY.setdefault(server_id, [])
                RESOURCE_HISTORY[server_id].append({
                    't': time.strftime('%H:%M:%S'), 'cpu': round(cpu, 1), 'ram_mb': round(ram_mb, 1)
                })
                if len(RESOURCE_HISTORY[server_id]) > 60:
                    RESOURCE_HISTORY[server_id] = RESOURCE_HISTORY[server_id][-60:]

                # High resource alert
                wh = CONFIG.get('webhooks', {})
                if cpu >= wh.get('cpu_alert_threshold', 90):
                    notify_event('high_cpu', server_id, f"CPU usage: {cpu:.1f}%")

            save_resource_history(RESOURCE_HISTORY)
        except Exception as e:
            print(f"Resource history error: {e}")

threading.Thread(target=resource_history_collector, daemon=True).start()

# =============================================================================
# AUTH ROUTES
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ban_info = _current_ban()
        if ban_info:
            return render_template('login.html', error=ban_info['message'], config=CONFIG, themes=THEMES, banned=True)
        password = request.form.get('password', '')
        username = request.form.get('username', '').strip()
        hashed = hashlib.sha256(password.encode()).hexdigest()

        matched_user = None
        matched_uid = None
        want_trust = request.form.get('trust_device') == '1'

        # 1) Try multi-user DB first (match by username+password, or password-only if no username given)
        for uid, u in USERS.items():
            if u.get('password_hash') == hashed:
                if username and u.get('username', '').lower() != username.lower():
                    continue
                matched_user = u
                matched_uid = uid
                break

        if matched_user:
            allowed, block_msg = _gate_device_login(want_trust)
            if not allowed:
                log_activity("Login Blocked", f"User '{matched_user.get('username')}' — correct password, device awaiting approval", "unknown")
                return render_template('login.html', error=block_msg, config=CONFIG, themes=THEMES, device_pending=True)
            session['logged_in'] = True
            session['is_admin'] = True
            session['login_time'] = time.time()
            session['username'] = matched_user.get('username')
            session['user_id'] = matched_uid
            session['role_label'] = 'ADMIN'
            session.permanent = True
            _clear_fail()
            ok = _mark_device_cookie(trust=want_trust)
            _save_devices()
            if ok:
                log_activity("Trusted Device", f"Device '{DEVICES.get(_device_cookie_id(), {}).get('label','')}' self-approved (slot {_count_trusted()}/{MAX_SELF_TRUST})", "admin")
            log_activity("Login", f"User '{matched_user.get('username')}' logged in (ADMIN)", "admin")
            return redirect(url_for('index'))

        # 2) Legacy fallback: old single admin/user password system (both grant ADMIN MODE)
        if hashed == CONFIG['passwords']['secret']:
            allowed, block_msg = _gate_device_login(want_trust)
            if not allowed:
                log_activity("Login Blocked", "Admin password correct — device awaiting approval", "unknown")
                return render_template('login.html', error=block_msg, config=CONFIG, themes=THEMES, device_pending=True)
            session['logged_in'] = True
            session['is_admin'] = True
            session['login_time'] = time.time()
            session['username'] = 'admin'
            session['role_label'] = 'ADMIN'
            session.permanent = True
            _clear_fail()
            ok = _mark_device_cookie(trust=want_trust)
            _save_devices()
            if ok:
                log_activity("Trusted Device", f"Device '{DEVICES.get(_device_cookie_id(), {}).get('label','')}' self-approved (slot {_count_trusted()}/{MAX_SELF_TRUST})", "admin")
            log_activity("Login", "Admin logged in", "admin")
            return redirect(url_for('index'))
        elif hashed == CONFIG['passwords']['user']:
            allowed, block_msg = _gate_device_login(want_trust)
            if not allowed:
                log_activity("Login Blocked", "User password correct — device awaiting approval", "unknown")
                return render_template('login.html', error=block_msg, config=CONFIG, themes=THEMES, device_pending=True)
            session['logged_in'] = True
            session['is_admin'] = True
            session['login_time'] = time.time()
            session['username'] = 'user'
            session['role_label'] = 'ADMIN'
            session.permanent = True
            _clear_fail()
            ok = _mark_device_cookie(trust=want_trust)
            _save_devices()
            if ok:
                log_activity("Trusted Device", f"Device '{DEVICES.get(_device_cookie_id(), {}).get('label','')}' self-approved (slot {_count_trusted()}/{MAX_SELF_TRUST})", "admin")
            log_activity("Login", "User logged in (ADMIN)", "admin")
            return redirect(url_for('index'))
        else:
            ban_note = _record_login_fail()
            log_activity("Login Failed", f"Invalid credentials (user: {username or 'n/a'})", "unknown")
            if ban_note:
                return render_template('login.html', error=ban_note, config=CONFIG, themes=THEMES, banned=True)
            remaining = MAX_LOGIN_FAILS - ban_fail_count()
            return render_template('login.html', error=f"Access Denied: Invalid credentials — আর {remaining} বার ভুল হলে এই IP ২৪ ঘণ্টার জন্য ban হবে", config=CONFIG, themes=THEMES)
    # GET — check if this IP is already banned
    ban_info = _current_ban()
    if ban_info:
        return render_template('login.html', error=ban_info['message'], config=CONFIG, themes=THEMES, banned=True)
    return render_template('login.html', config=CONFIG, themes=THEMES)

@app.route('/logout')
def logout():
    log_activity("Logout", "User logged out", get_current_role())
    session.clear()
    return redirect(url_for('login'))

# =============================================================================
# MAIN ROUTE
# =============================================================================

@app.route('/')
@login_required
def index():
    stats = get_system_stats()
    net_info = get_network_info()
    current_theme = THEMES.get(CONFIG.get('theme', 'pearl'), THEMES['pearl'])
    is_admin = True  # Single-role system: everyone logged in is ADMIN MODE
    serializable_servers = {}
    groups = set()
    for sid, s in SERVERS.items():
        serializable_servers[sid] = {
            'cmd': s.get('cmd', ''),
            'cwd': s.get('cwd', ''),
            'auto_restart': s.get('auto_restart', False),
            'restart_interval': s.get('restart_interval', '1h'),
            'status': s.get('status', 'stopped'),
            'path': s.get('path', ''),
            'last_start_time': s.get('last_start_time', 0),
            'created_at': s.get('created_at', 'Unknown'),
            'notes': s.get('notes', ''),
            'group': s.get('group', 'default'),
            'tags': s.get('tags', []),
            'uptime': format_uptime(int(time.time() - s.get('last_start_time', 0))) if s.get('status') == 'running' else '0m',
            'pid': s['process'].pid if s.get('process') else None
        }
        groups.add(s.get('group', 'default'))
    app_uptime = format_uptime(int(time.time() - START_TIME))
    health_map = {sid: compute_health_score(sid) for sid in SERVERS}
    tpl = render_template('index.html',
        servers=serializable_servers, stats=stats, net_info=net_info,
        total_count=len(SERVERS), running_count=sum(1 for s in SERVERS.values() if s['status'] == 'running'),
        config=CONFIG, theme=current_theme, themes=THEMES,
        is_admin=is_admin, app_uptime=app_uptime,
        username=session.get('username', 'user'),
        domains=DOMAINS, health_map=health_map,
        start_date=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(START_TIME)),
        groups=sorted(groups), base_dir=BASE_DIR if is_admin else '***')
    resp = make_response(tpl)
    resp.headers['Cache-Control'] = 'no-store'
    return resp

@app.route('/api/server/<server_id>/logs')
@login_required
def get_server_logs(server_id):
    if server_id not in SERVERS:
        return jsonify({'logs': ''})
    return jsonify({'logs': '\n'.join(SERVERS[server_id]['logs'][-500:])})

@app.route('/api/server/<server_id>/overview')
@login_required
def server_overview(server_id):
    """Powers the Pterodactyl-style stat cards + auto-detected Live Endpoint card."""
    if server_id not in SERVERS:
        return jsonify({'error': 'Server not found'}), 404
    s = SERVERS[server_id]
    stats = get_system_stats()
    net = get_network_info()
    endpoint = get_server_endpoint(server_id)
    usage = {'cpu': 0, 'mem_mb': 0}
    if s.get('process') and s.get('status') == 'running':
        usage = get_process_resource_usage(s['process'].pid)
    endpoint['url'] = (request.host_url.rstrip('/') + '/app/' + server_id + '/') if endpoint['live'] else None
    return jsonify({
        'address': f"{request.host}",
        'hostname': net['hostname'],
        'status': s.get('status', 'stopped'),
        'uptime': format_uptime(int(time.time() - s.get('last_start_time', time.time()))) if s.get('status') == 'running' else '0m',
        'cpu_percent': usage['cpu'],
        'mem_mb': usage['mem_mb'],
        'ram_total_mb': round(stats['ram_total'] * 1024, 0),
        'disk_used': stats['disk_used'], 'disk_total': stats['disk_total'],
        'net_sent': stats['net_sent'], 'net_recv': stats['net_recv'],
        'endpoint': endpoint
    })

@app.route('/api/server/<server_id>/endpoint')
@login_required
def server_endpoint_api(server_id):
    if server_id not in SERVERS:
        return jsonify({'error': 'Server not found'}), 404
    info = get_server_endpoint(server_id)
    info['url'] = (request.host_url.rstrip('/') + '/app/' + server_id + '/') if info['live'] else None
    return jsonify(info)

_PROXY_WAIT_HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<title>Waiting for app...</title>
<style>
body{background:#0a0a0a;color:#8fe38f;font-family:Consolas,monospace;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;text-align:center}
.box{padding:2rem}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#8fe38f;
animation:blink 1s infinite ease-in-out;margin-right:8px}
@keyframes blink{0%,100%{opacity:.2}50%{opacity:1}}
</style></head><body><div class="box">
<p><span class="dot"></span>No open port detected yet for <b>{{ server_id }}</b></p>
<p style="opacity:.6;font-size:.85rem">Start the server and make sure it binds to 0.0.0.0 (or 127.0.0.1) on any port.
This page auto-refreshes and will open your app as soon as a port is detected.</p>
{% if error %}<p style="opacity:.5;font-size:.75rem;color:#ff6b6b">{{ error }}</p>{% endif %}
</div></body></html>
"""

_HOP_BY_HOP = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
               'te', 'trailers', 'transfer-encoding', 'upgrade', 'content-encoding', 'content-length'}

@app.route('/app/<server_id>/', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
@app.route('/app/<server_id>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy_app(server_id, subpath):
    """Reverse-proxies http://127.0.0.1:<auto-detected-port>/... so a locally
    running app (Flask/Node/etc started by a server) is reachable at a clean,
    stable public path: https://<panel-host>/app/<server_id>/
    Intentionally PUBLIC (no @login_required) - this is the hosted site/tool
    itself, meant for anyone to open. The admin dashboard ('/') and every
    /api/* management route stay behind the username+password login."""
    if server_id not in SERVERS:
        abort(404)
    info = get_server_endpoint(server_id)
    if not info['live']:
        return render_template_string(_PROXY_WAIT_HTML, server_id=server_id, error=None), 503

    target = f"http://127.0.0.1:{info['port']}/{subpath}"
    fwd_headers = {k: v for k, v in request.headers if k.lower() not in ('host', 'cookie')}

    try:
        upstream = requests.request(
            method=request.method,
            url=target,
            params=request.args,
            headers=fwd_headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return render_template_string(_PROXY_WAIT_HTML, server_id=server_id, error=str(e)), 502

    content = upstream.content
    prefix = f"/app/{server_id}/"
    content_type = upstream.headers.get('Content-Type', '')

    # Best-effort so root-relative asset/link paths inside the proxied page
    # still resolve under /app/<server_id>/ instead of the panel's own root.
    if 'text/html' in content_type:
        try:
            html = content.decode(upstream.encoding or 'utf-8', errors='ignore')
            if re.search(r'<base[\s>]', html, re.IGNORECASE):
                pass
            elif re.search(r'<head[^>]*>', html, re.IGNORECASE):
                html = re.sub(r'(<head[^>]*>)', r'\1<base href="' + prefix + '">', html, count=1, flags=re.IGNORECASE)
            else:
                html = f'<base href="{prefix}">' + html
            content = html.encode('utf-8')
        except Exception:
            pass

    resp_headers = [(k, v) for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP]
    if upstream.status_code in (301, 302, 303, 307, 308) and 'Location' in upstream.headers:
        loc = upstream.headers['Location']
        if loc.startswith('/') and not loc.startswith(prefix):
            loc = prefix.rstrip('/') + loc
            resp_headers = [(k, v) for k, v in resp_headers if k.lower() != 'location'] + [('Location', loc)]

    return Response(content, status=upstream.status_code, headers=resp_headers)

def _server_id_for_live_port(port):
    """Find which running SERVERS entry currently owns this port. Only ports
    that are actually open by a server we started are proxyable - this keeps
    the short /<port>/ public alias from turning into an open SSRF proxy to
    arbitrary internal services."""
    for sid in SERVERS:
        info = get_server_endpoint(sid)
        if info['live'] and info['port'] == port:
            return sid
    return None

@app.route('/<int:port>/', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
@app.route('/<int:port>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy_by_port(port, subpath):
    """Short public alias, e.g. https://<panel-host>/64666/ -> same as
    /app/<server_id>/ but addressed directly by the local port a hosted app
    is listening on. Public by design, same as proxy_app."""
    server_id = _server_id_for_live_port(port)
    if not server_id:
        abort(404)
    return proxy_app(server_id, subpath)

@app.route('/api/system/stats')
@login_required
def system_stats():
    return jsonify(get_system_stats())

@app.route('/api/system/info')
@login_required
def system_info():
    try:
        info = {
            'platform': platform.platform(), 'processor': platform.processor() or 'Unknown',
            'architecture': platform.architecture()[0], 'python_version': platform.python_version(),
            'hostname': socket.gethostname(), 'cpu_count': psutil.cpu_count(),
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
            'total_ram': round(psutil.virtual_memory().total/(1024**3),2),
            'swap': round(psutil.swap_memory().total/(1024**3),2),
            'boot_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(psutil.boot_time())),
            'users': [u.name for u in psutil.users()]
        }
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/processes')
@login_required
def get_processes():
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
            try:
                info = proc.info
                info['create_time'] = time.strftime('%H:%M:%S', time.localtime(info['create_time']))
                processes.append(info)
            except: pass
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        return jsonify({'processes': processes[:100]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/ports')
@login_required
def get_ports():
    try:
        connections = psutil.net_connections()
        ports = []
        for conn in connections:
            if conn.laddr:
                try: proc_name = psutil.Process(conn.pid).name() if conn.pid else ''
                except: proc_name = ''
                ports.append({'port': conn.laddr.port, 'address': conn.laddr.ip,
                              'status': conn.status or '', 'pid': conn.pid, 'name': proc_name})
        ports.sort(key=lambda x: x['port'])
        return jsonify({'ports': ports[:200]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activity')
@login_required
def get_activity():
    logs = load_json(ACTIVITY_LOG, [])
    return jsonify({'logs': list(reversed(logs))[:200]})

@app.route('/api/settings', methods=['GET'])
@login_required
def settings_get():
    safe_config = {k: v for k, v in CONFIG.items() if k != 'passwords'}
    return jsonify(safe_config)

# =============================================================================
# ADMIN-ONLY APIs
# =============================================================================

@app.route('/api/server/create', methods=['POST'])
@admin_required
def create_server():
    try:
        data = request.get_json() or request.form
        server_name = data.get('server_name', '').strip().replace(' ', '_')
        start_command = data.get('start_command', '').strip()
        group = data.get('group', 'default').strip()
        notes = data.get('notes', '').strip()
        if not server_name: return jsonify({'error': 'Server name required'}), 400
        if server_name in SERVERS: return jsonify({'error': 'Server name already exists'}), 400
        server_path = os.path.join(UPLOAD_FOLDER, server_name)
        os.makedirs(server_path, exist_ok=True)
        SERVERS[server_name] = {
            'process': None, 'cmd': start_command, 'cwd': '',
            'logs': [f">>> [FX HOSTING] Server '{server_name}' created at {time.strftime('%Y-%m-%d %H:%M:%S')}"],
            'auto_restart': False, 'restart_interval': '1h', 'last_start_time': 0,
            'status': 'stopped', 'path': server_path,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'notes': notes, 'group': group, 'tags': [], 'env_vars': {}
        }
        save_servers()
        log_activity("Create Server", f"Created server '{server_name}'", "admin")
        return jsonify({'status': 'ok', 'server_id': server_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/upload', methods=['POST'])
@admin_required
def upload_server_file():
    try:
        server_name = request.form.get('server_name', '').strip().replace(' ', '_')
        start_command = request.form.get('start_command', '').strip()
        group = request.form.get('group', 'default').strip()
        notes = request.form.get('notes', '').strip()
        if not server_name: return jsonify({'error': 'Server name required'}), 400
        if server_name in SERVERS: return jsonify({'error': 'Server name already exists'}), 400
        server_path = os.path.join(UPLOAD_FOLDER, server_name)
        os.makedirs(server_path, exist_ok=True)
        file = request.files.get('file')
        if file and file.filename:
            file_path = os.path.join(server_path, file.filename)
            file.save(file_path)
            if file.filename.lower().endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as z: z.extractall(server_path)
            elif file.filename.lower().endswith('.7z'):
                with py7zr.SevenZipFile(file_path, mode='r') as z: z.extractall(server_path)
        SERVERS[server_name] = {
            'process': None, 'cmd': start_command, 'cwd': '',
            'logs': [f">>> [FX HOSTING] Server '{server_name}' created with upload at {time.strftime('%Y-%m-%d %H:%M:%S')}"],
            'auto_restart': False, 'restart_interval': '1h', 'last_start_time': 0,
            'status': 'stopped', 'path': server_path,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'notes': notes, 'group': group, 'tags': [], 'env_vars': {}
        }
        save_servers()
        log_activity("Upload Server", f"Created server '{server_name}' with upload", "admin")
        return jsonify({'status': 'ok', 'server_id': server_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/<action>', methods=['POST'])
@login_required
def server_action_api(server_id, action):
    if server_id not in SERVERS:
        return jsonify({'error': 'Server not found'}), 404
    server = SERVERS[server_id]
    try:
        if action == 'start':
            start_server_internal(server_id, server)
            return jsonify({'status': 'ok'})
        elif action == 'stop':
            if server['process']: kill_process_completely(server['process'])
            server['process'] = None
            server['status'] = 'stopped'
            server['logs'].append(f">>> [FX HOSTING] Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            save_servers()
            log_activity("Stop", f"Server '{server_id}' stopped", "admin")
            notify_event('stop', server_id, "Server stopped manually")
            return jsonify({'status': 'ok'})
        elif action == 'restart':
            if server['process']: kill_process_completely(server['process'])
            server['process'] = None
            server['status'] = 'stopped'
            server['logs'].append(">>> [FX HOSTING] Manual restart triggered...")
            time.sleep(0.5)
            start_server_internal(server_id, server)
            return jsonify({'status': 'ok'})
        elif action == 'delete':
            if server['process']: kill_process_completely(server['process'])
            server['process'] = None
            if os.path.exists(server['path']): shutil.rmtree(server['path'], ignore_errors=True)
            del SERVERS[server_id]
            save_servers()
            log_activity("Delete", f"Server '{server_id}' deleted", "admin")
            return jsonify({'status': 'ok'})
        elif action == 'clone':
            new_name = (request.get_json() or {}).get('new_name', '').strip().replace(' ', '_')
            if not new_name or new_name in SERVERS:
                return jsonify({'error': 'Invalid clone name'}), 400
            new_path = os.path.join(UPLOAD_FOLDER, new_name)
            if os.path.exists(server['path']): shutil.copytree(server['path'], new_path)
            SERVERS[new_name] = {
                'process': None, 'cmd': server['cmd'], 'cwd': server.get('cwd', ''),
                'logs': [f">>> [FX HOSTING] Cloned from '{server_id}' at {time.strftime('%Y-%m-%d %H:%M:%S')}"],
                'auto_restart': False, 'restart_interval': '1h', 'last_start_time': 0,
                'status': 'stopped', 'path': new_path,
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'notes': f"Cloned from {server_id}", 'group': server.get('group', 'default'),
                'tags': list(server.get('tags', [])), 'env_vars': dict(server.get('env_vars', {}))
            }
            save_servers()
            log_activity("Clone", f"Server '{server_id}' cloned to '{new_name}'", "admin")
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'error': 'Invalid action'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/config', methods=['GET', 'POST'])
@admin_required
def server_config(server_id):
    if server_id not in SERVERS:
        return jsonify({'error': 'Server not found'}), 404
    if request.method == 'POST':
        data = request.get_json()
        if not data: return jsonify({'error': 'No data provided'}), 400
        SERVERS[server_id]['cmd'] = data.get('cmd', SERVERS[server_id]['cmd'])
        SERVERS[server_id]['cwd'] = data.get('cwd', SERVERS[server_id].get('cwd', ''))
        SERVERS[server_id]['auto_restart'] = data.get('auto_restart', SERVERS[server_id].get('auto_restart', False))
        SERVERS[server_id]['restart_interval'] = data.get('restart_interval', SERVERS[server_id].get('restart_interval', '1h'))
        SERVERS[server_id]['notes'] = data.get('notes', SERVERS[server_id].get('notes', ''))
        SERVERS[server_id]['group'] = data.get('group', SERVERS[server_id].get('group', 'default'))
        SERVERS[server_id]['env_vars'] = data.get('env_vars', SERVERS[server_id].get('env_vars', {}))
        save_servers()
        log_activity("Config Update", f"Server '{server_id}' config updated", "admin")
        return jsonify({'status': 'ok'})
    return jsonify({
        'cmd': SERVERS[server_id].get('cmd', ''), 'cwd': SERVERS[server_id].get('cwd', ''),
        'auto_restart': SERVERS[server_id].get('auto_restart', False),
        'restart_interval': SERVERS[server_id].get('restart_interval', '1h'),
        'notes': SERVERS[server_id].get('notes', ''), 'group': SERVERS[server_id].get('group', 'default'),
        'env_vars': SERVERS[server_id].get('env_vars', {}), 'created_at': SERVERS[server_id].get('created_at', 'Unknown')
    })

@app.route('/api/server/<server_id>/input', methods=['POST'])
@admin_required
def send_server_input(server_id):
    cmd = (request.get_json() or request.form).get('command', '')
    if not cmd or server_id not in SERVERS: return jsonify({'error': 'Invalid request'}), 400
    server = SERVERS[server_id]
    if not server['process']: return jsonify({'error': 'Process not running'}), 400
    try:
        proc = server['process']
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.write(cmd + '\n')
            proc.stdin.flush()
            server['logs'].append(f">>> [INPUT] {cmd}")
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'stdin closed'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/clear_logs', methods=['POST'])
@admin_required
def clear_server_logs(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    SERVERS[server_id]['logs'] = [f">>> [FX HOSTING] Logs cleared at {time.strftime('%Y-%m-%d %H:%M:%S')}"]
    return jsonify({'status': 'ok'})

# =============================================================================
# FILE MANAGEMENT (ADMIN ONLY)
# =============================================================================

@app.route('/api/files/<server_id>')
@admin_required
def list_files(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    subpath = request.args.get('path', '')
    base_path = SERVERS[server_id]['path']
    full_path = os.path.normpath(os.path.join(base_path, subpath)) if subpath else base_path
    if not os.path.realpath(full_path).startswith(os.path.realpath(base_path)):
        full_path = base_path; subpath = ''
    if not os.path.exists(full_path): return jsonify({'files': [], 'current_path': '', 'total_size': '0 B'})
    files = []
    total_size = 0
    for item in os.listdir(full_path):
        item_path = os.path.join(full_path, item)
        is_file = os.path.isfile(item_path)
        size = os.path.getsize(item_path) if is_file else 0
        total_size += size
        size_str = f"{size} B" if size < 1024 else (f"{size/1024:.1f} KB" if size < 1024**2 else f"{size/(1024**2):.1f} MB")
        files.append({'name': item, 'size': size_str, 'raw_size': size, 'type': 'file' if is_file else 'dir',
                      'ext': os.path.splitext(item)[1].lower() if is_file else '',
                      'modified': time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(item_path)))})
    files.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))
    total_str = f"{total_size} B" if total_size < 1024 else (f"{total_size/1024:.1f} KB" if total_size < 1024**2 else f"{total_size/(1024**2):.1f} MB")
    return jsonify({'files': files, 'current_path': subpath, 'total_size': total_str})

@app.route('/api/files/<server_id>/content')
@admin_required
def file_content(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    filename = request.args.get('filename', '')
    subpath = request.args.get('path', '')
    base_path = SERVERS[server_id]['path']
    file_path = os.path.normpath(os.path.join(base_path, subpath, filename))
    if not os.path.realpath(file_path).startswith(os.path.realpath(base_path)): return jsonify({'error': 'Invalid path'}), 400
    if not os.path.isfile(file_path): return jsonify({'error': 'File not found'}), 404
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f: content = f.read()
        return jsonify({'content': content, 'size': os.path.getsize(file_path)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/<server_id>/save', methods=['POST'])
@admin_required
def save_file_content(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    filename = data.get('filename', ''); subpath = data.get('path', ''); content = data.get('content', '')
    base_path = SERVERS[server_id]['path']
    file_path = os.path.normpath(os.path.join(base_path, subpath, filename))
    if not os.path.realpath(file_path).startswith(os.path.realpath(base_path)): return jsonify({'error': 'Invalid path'}), 400
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
        log_activity("File Save", f"Saved '{filename}' in '{server_id}'", "admin")
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/<server_id>/create', methods=['POST'])
@admin_required
def create_file_api(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    filename = data.get('filename', ''); subpath = data.get('path', ''); content = data.get('content', '')
    base_path = SERVERS[server_id]['path']
    file_path = os.path.normpath(os.path.join(base_path, subpath, filename))
    if not os.path.realpath(file_path).startswith(os.path.realpath(base_path)): return jsonify({'error': 'Invalid path'}), 400
    if os.path.exists(file_path): return jsonify({'error': 'File already exists'}), 400
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
        log_activity("File Create", f"Created '{filename}' in '{server_id}'", "admin")
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/<server_id>/mkdir', methods=['POST'])
@admin_required
def create_folder(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    name = data.get('name', ''); subpath = data.get('path', '')
    base_path = SERVERS[server_id]['path']
    target = os.path.normpath(os.path.join(base_path, subpath, name))
    if not os.path.realpath(target).startswith(os.path.realpath(base_path)): return jsonify({'error': 'Invalid path'}), 400
    os.makedirs(target, exist_ok=True)
    return jsonify({'status': 'ok'})

@app.route('/api/files/<server_id>/rename', methods=['POST'])
@admin_required
def rename_file(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    old_name = data.get('old_name', ''); new_name = data.get('new_name', ''); subpath = data.get('path', '')
    base_path = SERVERS[server_id]['path']
    old_path = os.path.normpath(os.path.join(base_path, subpath, old_name))
    new_path = os.path.normpath(os.path.join(base_path, subpath, new_name))
    if not os.path.realpath(old_path).startswith(os.path.realpath(base_path)): return jsonify({'error': 'Invalid path'}), 400
    if not os.path.exists(old_path): return jsonify({'error': 'File not found'}), 404
    os.rename(old_path, new_path)
    return jsonify({'status': 'ok'})

@app.route('/api/files/<server_id>/delete', methods=['POST'])
@admin_required
def delete_file(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    filename = data.get('filename', ''); subpath = data.get('path', '')
    base_path = SERVERS[server_id]['path']
    file_path = os.path.normpath(os.path.join(base_path, subpath, filename))
    if not os.path.realpath(file_path).startswith(os.path.realpath(base_path)): return jsonify({'error': 'Invalid path'}), 400
    if os.path.isdir(file_path): shutil.rmtree(file_path)
    else: os.remove(file_path)
    log_activity("Delete File", f"Deleted '{filename}' from '{server_id}'", "admin")
    return jsonify({'status': 'ok'})

@app.route('/api/files/<server_id>/upload', methods=['POST'])
@admin_required
def upload_file(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    subpath = request.form.get('path', '')
    file = request.files.get('file')
    if not file or not file.filename: return jsonify({'error': 'No file provided'}), 400
    base_path = SERVERS[server_id]['path']
    target_dir = os.path.normpath(os.path.join(base_path, subpath)) if subpath else base_path
    if not os.path.realpath(target_dir).startswith(os.path.realpath(base_path)): return jsonify({'error': 'Invalid path'}), 400
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, file.filename)
    file.save(file_path)
    msg = 'File uploaded successfully'
    if file.filename.lower().endswith('.zip'):
        with zipfile.ZipFile(file_path, 'r') as z: z.extractall(target_dir)
        msg = 'ZIP extracted successfully'
    elif file.filename.lower().endswith('.7z'):
        with py7zr.SevenZipFile(file_path, mode='r') as z: z.extractall(target_dir)
        msg = '7Z extracted successfully'
    log_activity("File Upload", f"Uploaded '{file.filename}' to '{server_id}'", "admin")
    return jsonify({'status': 'ok', 'message': msg})

@app.route('/api/files/<server_id>/download')
@admin_required
def download_file(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    import io
    filename = request.args.get('filename', ''); subpath = request.args.get('path', '')
    base_path = SERVERS[server_id]['path']
    file_path = os.path.normpath(os.path.join(base_path, subpath, filename))
    if not os.path.realpath(file_path).startswith(os.path.realpath(base_path)): return jsonify({'error': 'Invalid path'}), 400
    if not os.path.exists(file_path): return jsonify({'error': 'File not found'}), 404
    if os.path.isdir(file_path):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(file_path):
                for f in files:
                    abs_path = os.path.join(root, f)
                    arcname = os.path.relpath(abs_path, os.path.dirname(file_path))
                    zf.write(abs_path, arcname)
        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name=filename+'.zip', mimetype='application/zip')
    return send_file(file_path, as_attachment=True)

@app.route('/api/files/<server_id>/extract', methods=['POST'])
@admin_required
def extract_archive(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    filename = data.get('filename', ''); subpath = data.get('path', '')
    base_path = SERVERS[server_id]['path']
    archive_path = os.path.normpath(os.path.join(base_path, subpath, filename))
    if not os.path.exists(archive_path): return jsonify({'error': 'Archive not found'}), 404
    extract_to = os.path.dirname(archive_path)
    try:
        lower = filename.lower()
        if lower.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as z: z.extractall(extract_to)
        elif lower.endswith('.7z'):
            with py7zr.SevenZipFile(archive_path, mode='r') as z: z.extractall(extract_to)
        elif lower.endswith('.tar.gz') or lower.endswith('.tgz') or lower.endswith('.tar.bz2') or \
             lower.endswith('.tbz2') or lower.endswith('.tar.xz') or lower.endswith('.txz') or lower.endswith('.tar'):
            import tarfile
            with tarfile.open(archive_path, 'r:*') as t: t.extractall(extract_to)
        elif lower.endswith('.gz'):
            import gzip
            out_name = filename[:-3] if filename[:-3] else filename + '.out'
            out_path = os.path.join(extract_to, out_name)
            with gzip.open(archive_path, 'rb') as f_in, open(out_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        else: return jsonify({'error': 'Unsupported format'}), 400
        log_activity("Extract Archive", f"Extracted '{filename}' in '{server_id}'", "admin")
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# PACKAGE MANAGER (ADMIN ONLY)
# =============================================================================

@app.route('/api/packages/<server_id>/install', methods=['POST'])
@admin_required
def install_package(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    pkg_type = data.get('type', 'pip'); pkg_name = data.get('name', '').strip()
    if not pkg_name: return jsonify({'error': 'Package name required'}), 400
    import re as _re
    if not _re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]*$', pkg_name): return jsonify({'error': 'Invalid package name'}), 400
    pkg_type = pkg_type if pkg_type in ('pip', 'pip3', 'npm', 'apt', 'apt-get', 'pkg', 'gem', 'apk') else 'pip'
    commands = {'pip': f"pip install --break-system-packages {pkg_name} || pip install {pkg_name}", 'pip3': f"pip3 install --break-system-packages {pkg_name} || pip3 install {pkg_name}", 'npm': f"npm install {pkg_name}", 'apt': f"apt install -y {pkg_name}", 'apt-get': f"apt-get install -y {pkg_name}", 'pkg': f"pkg install -y {pkg_name}", 'gem': f"gem install {pkg_name}", 'apk': f"apk add {pkg_name}"}
    cmd = commands.get(pkg_type, f"pip install --break-system-packages {pkg_name} || pip install {pkg_name}")
    SERVERS[server_id]['logs'].append(f">>> [FX HOSTING] Installing {pkg_name} via {pkg_type}...")
    def run_install():
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            output_lines = []
            for line in iter(process.stdout.readline, ''):
                if line: output_lines.append(line.strip()); SERVERS[server_id]['logs'].append(line.strip())
            rc = process.wait()
            if rc != 0 and any('Permission denied' in l or 'error' in l.lower() for l in output_lines):
                SERVERS[server_id]['logs'].append(f">>> [FX HOSTING] Retrying with python3 -m pip...")
                retry_cmd = cmd.replace('pip install', 'python3 -m pip install --break-system-packages').replace('pip3 install', 'python3 -m pip install --break-system-packages')
                if retry_cmd != cmd:
                    process2 = subprocess.Popen(retry_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                    for line in iter(process2.stdout.readline, ''):
                        if line: SERVERS[server_id]['logs'].append(line.strip())
            SERVERS[server_id]['logs'].append(f">>> [FX HOSTING] Installation of {pkg_name} completed.")
        except Exception as e:
            SERVERS[server_id]['logs'].append(f">>> [FX HOSTING] Install error: {str(e)}")
    threading.Thread(target=run_install, daemon=True).start()
    log_activity("Package Install", f"Installed '{pkg_name}' ({pkg_type}) on '{server_id}'", "admin")
    return jsonify({'status': 'ok'})

@app.route('/api/packages/<server_id>/uninstall', methods=['POST'])
@admin_required
def uninstall_package(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    pkg_type = data.get('type', 'pip'); pkg_name = data.get('name', '').strip()
    if not pkg_name: return jsonify({'error': 'Package name required'}), 400
    import re as _re
    if not _re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]*$', pkg_name): return jsonify({'error': 'Invalid package name'}), 400
    pkg_type = pkg_type if pkg_type in ('pip', 'pip3', 'npm', 'apt', 'apt-get', 'pkg', 'gem', 'apk') else 'pip'
    commands = {'pip': f"pip uninstall --user -y {pkg_name}", 'pip3': f"pip3 uninstall --user -y {pkg_name}", 'npm': f"npm uninstall {pkg_name}", 'apt': f"apt remove -y {pkg_name}", 'apt-get': f"apt-get remove -y {pkg_name}", 'pkg': f"pkg uninstall -y {pkg_name}", 'gem': f"gem uninstall -y {pkg_name}", 'apk': f"apk del {pkg_name}"}
    cmd = commands.get(pkg_type, f"pip uninstall -y {pkg_name}")
    SERVERS[server_id]['logs'].append(f">>> [FX HOSTING] Uninstalling {pkg_name}...")
    def run_uninst():
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in iter(process.stdout.readline, ''):
                if line: SERVERS[server_id]['logs'].append(line.strip())
            SERVERS[server_id]['logs'].append(f">>> [FX HOSTING] Uninstallation complete.")
        except Exception as e:
            SERVERS[server_id]['logs'].append(f">>> [FX HOSTING] Uninstall error: {str(e)}")
    threading.Thread(target=run_uninst, daemon=True).start()
    return jsonify({'status': 'ok'})

@app.route('/api/packages/<server_id>/list')
@admin_required
def list_packages(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    pkg_type = request.args.get('type', 'pip')
    commands = {'pip': "pip list --format=json", 'npm': "npm list --depth=0 --json", 'apt': "apt list --installed 2>/dev/null | head -50"}
    cmd = commands.get(pkg_type, "pip list --format=json")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return jsonify({'output': result.stdout[:5000] or 'No packages found'})
    except:
        return jsonify({'output': 'Failed to list packages'})

# =============================================================================
# BACKUP MANAGER (ADMIN ONLY)
# =============================================================================

@app.route('/api/backup/<server_id>/create', methods=['POST'])
@admin_required
def create_backup(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    try:
        backup_dir = os.path.join(BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        backup_name = f"{server_id}_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_name)
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(SERVERS[server_id]['path']):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, SERVERS[server_id]['path'])
                    zf.write(file_path, arcname)
        log_activity("Backup", f"Created backup '{backup_name}' for '{server_id}'", "admin")
        return jsonify({'status': 'ok', 'backup_name': backup_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/<server_id>/restore', methods=['POST'])
@admin_required
def restore_backup(server_id):
    if server_id not in SERVERS: return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    backup_name = os.path.basename(data.get('backup_name', ''))
    backup_path = os.path.join(BASE_DIR, 'backups', backup_name)
    if not os.path.exists(backup_path): return jsonify({'error': 'Backup not found'}), 404
    try:
        if SERVERS[server_id].get('status') == 'running' and SERVERS[server_id].get('process'):
            kill_process_completely(SERVERS[server_id]['process'])
            SERVERS[server_id]['process'] = None
            SERVERS[server_id]['status'] = 'stopped'
        if os.path.exists(SERVERS[server_id]['path']): shutil.rmtree(SERVERS[server_id]['path'])
        os.makedirs(SERVERS[server_id]['path'], exist_ok=True)
        with zipfile.ZipFile(backup_path, 'r') as zf: zf.extractall(SERVERS[server_id]['path'])
        log_activity("Restore", f"Restored backup '{backup_name}' to '{server_id}'", "admin")
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/list')
@login_required
def list_backups():
    backup_dir = os.path.join(BASE_DIR, 'backups')
    if not os.path.exists(backup_dir): return jsonify({'backups': []})
    backups = []
    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.endswith('.zip'):
            fpath = os.path.join(backup_dir, f)
            size = os.path.getsize(fpath)
            size_str = f"{size/1024:.1f} KB" if size < 1024**2 else f"{size/(1024**2):.1f} MB"
            backups.append({'name': f, 'size': size_str, 'date': time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(fpath)))})
    return jsonify({'backups': backups})

@app.route('/api/backup/delete', methods=['POST'])
@admin_required
def delete_backup():
    data = request.get_json() or request.form
    backup_name = data.get('backup_name', '').replace('..', '')
    backup_path = os.path.join(BASE_DIR, 'backups', backup_name)
    if os.path.exists(backup_path): os.remove(backup_path); return jsonify({'status': 'ok'})
    return jsonify({'error': 'Backup not found'}), 404

# =============================================================================
# FULL SYSTEM BACKUP / RESTORE (ADMIN ONLY)
# One single .zip containing ALL servers' files + full details
# (start command, cwd, auto_restart, restart_interval, notes, group, tags,
# env_vars, created_at, status) so the entire panel state can be restored
# on this or any other FX HOSTING instance by re-uploading the zip.
# =============================================================================

@app.route('/api/backup/full/download')
@admin_required
def download_full_backup():
    import io
    try:
        manifest = {
            'type': 'FX_HOSTING_FULL_BACKUP',
            'version': 1,
            'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'servers': {}
        }
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for sid, s in SERVERS.items():
                manifest['servers'][sid] = {
                    'cmd': s.get('cmd', ''),
                    'cwd': s.get('cwd', ''),
                    'auto_restart': s.get('auto_restart', False),
                    'restart_interval': s.get('restart_interval', '1h'),
                    'status': s.get('status', 'stopped'),
                    'created_at': s.get('created_at', ''),
                    'notes': s.get('notes', ''),
                    'group': s.get('group', 'default'),
                    'tags': s.get('tags', []),
                    'env_vars': s.get('env_vars', {})
                }
                base_path = s.get('path', '')
                if base_path and os.path.isdir(base_path):
                    for root, dirs, files in os.walk(base_path):
                        for f in files:
                            abs_path = os.path.join(root, f)
                            arcname = os.path.join('servers', sid, os.path.relpath(abs_path, base_path))
                            zf.write(abs_path, arcname)
            zf.writestr('manifest.json', json.dumps(manifest, indent=2))
        zip_buffer.seek(0)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        download_name = f"FX_HOSTING_FULL_BACKUP_{timestamp}.zip"
        log_activity("Full Backup", f"Downloaded full system backup ({len(manifest['servers'])} servers)", "admin")
        return send_file(zip_buffer, as_attachment=True, download_name=download_name, mimetype='application/zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/full/restore', methods=['POST'])
@admin_required
def restore_full_backup():
    file = request.files.get('backup_file')
    if not file or not file.filename:
        return jsonify({'error': 'No backup file uploaded'}), 400
    backups_dir = os.path.join(BASE_DIR, 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    tmp_path = os.path.join(backups_dir, f"__full_restore_{secrets.token_hex(6)}.zip")
    try:
        file.save(tmp_path)
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            names = zf.namelist()
            if 'manifest.json' not in names:
                return jsonify({'error': 'Invalid backup file: manifest.json missing'}), 400
            manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
            if manifest.get('type') != 'FX_HOSTING_FULL_BACKUP':
                return jsonify({'error': 'Invalid backup file: not an FX HOSTING full backup'}), 400

            replace_all = str(request.form.get('replace_all', 'true')).lower() != 'false'

            # Stop every currently running server before touching disk state
            for sid, s in list(SERVERS.items()):
                if s.get('process'):
                    try: kill_process_completely(s['process'])
                    except Exception: pass
                    s['process'] = None
                    s['status'] = 'stopped'

            if replace_all:
                # Make current state exactly match the backup: drop servers not in it
                for sid in list(SERVERS.keys()):
                    if sid not in manifest.get('servers', {}):
                        if os.path.exists(SERVERS[sid]['path']):
                            shutil.rmtree(SERVERS[sid]['path'], ignore_errors=True)
                        del SERVERS[sid]

            restored = 0
            for sid, meta in manifest.get('servers', {}).items():
                server_path = os.path.join(UPLOAD_FOLDER, sid)
                if os.path.exists(server_path):
                    shutil.rmtree(server_path, ignore_errors=True)
                os.makedirs(server_path, exist_ok=True)
                prefix = f"servers/{sid}/"
                for name in names:
                    if name.startswith(prefix) and not name.endswith('/'):
                        rel = name[len(prefix):]
                        target = os.path.normpath(os.path.join(server_path, rel))
                        if not os.path.realpath(target).startswith(os.path.realpath(server_path)):
                            continue
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        with zf.open(name) as src, open(target, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                SERVERS[sid] = {
                    'process': None,
                    'cmd': meta.get('cmd', ''),
                    'cwd': meta.get('cwd', ''),
                    'logs': [f">>> [FX HOSTING] Restored from full backup at {time.strftime('%Y-%m-%d %H:%M:%S')}"],
                    'auto_restart': meta.get('auto_restart', False),
                    'restart_interval': meta.get('restart_interval', '1h'),
                    'last_start_time': 0,
                    'status': 'stopped',
                    'path': server_path,
                    'created_at': meta.get('created_at', time.strftime('%Y-%m-%d %H:%M:%S')),
                    'notes': meta.get('notes', ''),
                    'group': meta.get('group', 'default'),
                    'tags': meta.get('tags', []),
                    'env_vars': meta.get('env_vars', {})
                }
                restored += 1

        save_servers()
        log_activity("Full Restore", f"Restored {restored} servers from full system backup", "admin")
        return jsonify({'status': 'ok', 'restored': restored})
    except zipfile.BadZipFile:
        return jsonify({'error': 'Invalid zip file'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# =============================================================================
# TERMINAL (ADMIN ONLY)
# =============================================================================

@app.route('/api/terminal/execute', methods=['POST'])
@admin_required
def terminal_execute():
    data = request.get_json() or request.form
    command = data.get('command', '').strip()
    cwd = data.get('cwd', None)
    if not command: return jsonify({'error': 'No command provided'}), 400
    dangerous = ['rm -rf /', 'mkfs', 'dd if=/dev/zero', ':(){:|:&};:', '> /dev/sda']
    for d in dangerous:
        if d in command:
            return jsonify({'output': f'\x1b[31mBlocked: dangerous command detected ({d})\x1b[0m', 'returncode': 403, 'cwd': cwd or BASE_DIR})
    work_dir = cwd if (cwd and os.path.isdir(cwd)) else BASE_DIR
    if command.startswith('cd ') or command == 'cd':
        target = command[3:].strip() if command != 'cd' else os.path.expanduser('~')
        target = os.path.expanduser(target)
        if not os.path.isabs(target): target = os.path.normpath(os.path.join(work_dir, target))
        if os.path.isdir(target): return jsonify({'output': '', 'returncode': 0, 'cwd': target})
        else: return jsonify({'output': f'cd: {target}: No such file or directory', 'returncode': 1, 'cwd': work_dir})
    try:
        result = subprocess.run(command, shell=True, cwd=work_dir, capture_output=True, text=True, timeout=60, env={**os.environ, 'TERM': 'xterm-256color'})
        output = result.stdout + result.stderr
        log_activity("Terminal", f"CMD: {command[:80]}", "admin")
        return jsonify({'output': output[:50000], 'returncode': result.returncode, 'cwd': work_dir})
    except subprocess.TimeoutExpired:
        return jsonify({'output': 'Command timed out (60s)', 'returncode': -1, 'cwd': work_dir})
    except Exception as e:
        return jsonify({'output': str(e), 'returncode': -1, 'cwd': work_dir})

@app.route('/api/terminal/autocomplete', methods=['POST'])
@admin_required
def terminal_autocomplete():
    data = request.get_json() or {}
    prefix = data.get('prefix', ''); cwd = data.get('cwd', BASE_DIR)
    try:
        if not os.path.isdir(cwd): cwd = BASE_DIR
        parts = prefix.split('/'); partial = parts[-1]; parent = '/'.join(parts[:-1]) if len(parts) > 1 else ''
        search_dir = os.path.join(cwd, parent) if parent else cwd
        if not os.path.isdir(search_dir): search_dir = cwd
        matches = []
        for item in os.listdir(search_dir):
            if item.startswith(partial):
                full = (parent + '/' + item) if parent else item
                if os.path.isdir(os.path.join(search_dir, item)): full += '/'
                matches.append(full)
        return jsonify({'matches': sorted(matches)[:20]})
    except:
        return jsonify({'matches': []})

# =============================================================================
# PROCESS KILLER (ADMIN ONLY)
# =============================================================================

@app.route('/api/system/kill_process', methods=['POST'])
@admin_required
def kill_system_process():
    data = request.get_json() or request.form
    pid = data.get('pid')
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid PID'}), 400
    try:
        p = psutil.Process(pid_int)
        p.kill()
        log_activity("Process Kill", f"Killed PID {pid_int}", "admin")
        return jsonify({'status': 'ok'})
    except psutil.NoSuchProcess:
        return jsonify({'error': f'No such process: PID {pid_int} (already stopped?)'}), 404
    except psutil.AccessDenied:
        return jsonify({'error': f'Access denied: cannot kill PID {pid_int} (permission issue)'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# BULK OPERATIONS (ADMIN ONLY)
# =============================================================================

@app.route('/api/bulk/upload', methods=['POST'])
@admin_required
def bulk_upload():
    file = request.files.get('file')
    if not file or not file.filename: return jsonify({'error': 'No file provided'}), 400
    results = {}; file_bytes = file.read(); filename = file.filename
    for server_id, server in SERVERS.items():
        try:
            base_path = server.get('path', '')
            if not base_path or not os.path.exists(base_path):
                results[server_id] = {'status': 'error', 'message': 'Path not found'}; continue
            file_path = os.path.join(base_path, filename)
            with open(file_path, 'wb') as f: f.write(file_bytes)
            msg = 'Uploaded'
            if filename.lower().endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as z: z.extractall(base_path); msg = 'ZIP extracted'
            results[server_id] = {'status': 'ok', 'message': msg}
        except Exception as e:
            results[server_id] = {'status': 'error', 'message': str(e)}
    log_activity("Bulk Upload", f"File '{filename}' uploaded to {len(SERVERS)} servers", "admin")
    return jsonify({'status': 'ok', 'results': results, 'total': len(SERVERS)})

@app.route('/api/bulk/start_command', methods=['POST'])
@admin_required
def bulk_start_command():
    data = request.get_json() or request.form
    cmd = data.get('command', '').strip()
    if not cmd: return jsonify({'error': 'No command provided'}), 400
    results = {}
    for server_id in SERVERS:
        try: SERVERS[server_id]['cmd'] = cmd; results[server_id] = {'status': 'ok'}
        except Exception as e: results[server_id] = {'status': 'error', 'message': str(e)}
    save_servers()
    return jsonify({'status': 'ok', 'results': results, 'total': len(SERVERS)})

@app.route('/api/bulk/action', methods=['POST'])
@admin_required
def bulk_action():
    """Start/Stop/Restart ALL servers at once"""
    data = request.get_json() or request.form
    action = data.get('action', '')
    server_ids = data.get('server_ids', list(SERVERS.keys()))
    results = {}
    for server_id in server_ids:
        if server_id not in SERVERS: continue
        server = SERVERS[server_id]
        try:
            if action == 'start':
                start_server_internal(server_id, server); results[server_id] = 'started'
            elif action == 'stop':
                if server['process']: kill_process_completely(server['process'])
                server['process'] = None; server['status'] = 'stopped'; results[server_id] = 'stopped'
            elif action == 'restart':
                if server['process']: kill_process_completely(server['process'])
                server['process'] = None; server['status'] = 'stopped'
                time.sleep(0.3); start_server_internal(server_id, server); results[server_id] = 'restarted'
        except Exception as e:
            results[server_id] = f'error: {str(e)}'
    save_servers()
    log_activity(f"Bulk {action.title()}", f"Action on {len(results)} servers", "admin")
    return jsonify({'status': 'ok', 'results': results})

# =============================================================================
# SETTINGS (ADMIN ONLY for write)
# =============================================================================

@app.route('/api/settings', methods=['POST'])
@admin_required
def settings_update():
    global CONFIG
    data = request.get_json() or request.form
    CONFIG['site_title'] = data.get('site_title', CONFIG['site_title'])
    CONFIG['site_header'] = data.get('site_header', CONFIG['site_header'])
    CONFIG['icon_url'] = data.get('icon_url', CONFIG['icon_url'])
    CONFIG['theme'] = data.get('theme', CONFIG['theme'])
    CONFIG['font_family'] = data.get('font_family', CONFIG.get('font_family', 'terminal'))
    CONFIG['terminal_height'] = int(data.get('terminal_height', CONFIG.get('terminal_height', 300)))
    CONFIG['auto_refresh'] = data.get('auto_refresh', 'true') == 'true'
    CONFIG['notifications'] = data.get('notifications', 'true') == 'true'
    CONFIG['show_system_stats'] = data.get('show_system_stats', 'true') == 'true'
    if 'jwt_api_url' in data:
        CONFIG['jwt_api_url'] = (data.get('jwt_api_url') or '').strip() or CONFIG.get('jwt_api_url', '')
    if 'jwt_api_key' in data:
        # key is optional — an explicitly blank value is honored (clears it),
        # unlike the URL which always needs a real value
        CONFIG['jwt_api_key'] = (data.get('jwt_api_key') or '').strip()
    save_json(CONFIG_FILE, CONFIG)
    log_activity("Settings", "Application settings updated", "admin")
    return jsonify({'status': 'ok'})

@app.route('/api/settings/password', methods=['POST'])
@login_required
def change_password_api():
    global CONFIG
    data = request.get_json() or request.form
    current = data.get('current', ''); new_pass = data.get('new', '')
    hashed_current = hashlib.sha256(current.encode()).hexdigest()
    target = data.get('target', 'user')
    if target == 'secret' and not session.get('is_admin'):
        return jsonify({'error': 'Admin access required'}), 403
    if hashed_current != CONFIG['passwords'].get(target, ''):
        return jsonify({'error': 'Current password incorrect'}), 400
    CONFIG['passwords'][target] = hashlib.sha256(new_pass.encode()).hexdigest()
    save_json(CONFIG_FILE, CONFIG)
    log_activity("Password Change", f"{target} password changed", get_current_role())
    return jsonify({'status': 'ok'})

# =============================================================================
# TELEGRAM BOT DEPLOY (ADMIN ONLY)
# =============================================================================

@app.route('/api/telegram/deploy', methods=['POST'])
@admin_required
def deploy_telegram_bot():
    data = request.get_json() or request.form
    bot_token = data.get('token', '').strip()
    bot_name = data.get('name', 'TelegramBot').strip().replace(' ', '_')
    if not bot_token or ':' not in bot_token: return jsonify({'error': 'Invalid bot token'}), 400
    if bot_name in SERVERS: return jsonify({'error': 'Server name already exists'}), 400
    server_path = os.path.join(UPLOAD_FOLDER, bot_name)
    os.makedirs(server_path, exist_ok=True)
    bot_code = f'''#!/usr/bin/env python3
"""Telegram Bot - Auto Generated by FX HOSTING"""
import asyncio, logging, sys
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "{bot_token}"
router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("<b>FX HOSTING Bot\\n\\n/start /help /ping /status</b>", parse_mode=ParseMode.HTML)

@router.message(Command("ping"))
async def cmd_ping(message: types.Message):
    import time
    start = time.time()
    msg = await message.answer("Pinging...")
    elapsed = (time.time() - start) * 1000
    await msg.edit_text(f"<b>Pong!</b>\\nLatency: {{elapsed:.1f}}ms", parse_mode=ParseMode.HTML)

@router.message(Command("status"))
async def cmd_status(message: types.Message):
    import psutil
    cpu = psutil.cpu_percent(interval=0.5); ram = psutil.virtual_memory().percent; disk = psutil.disk_usage('/').percent
    await message.answer(f"<b>System Status</b>\\nCPU: {{cpu}}%\\nRAM: {{ram}}%\\nDisk: {{disk}}%", parse_mode=ParseMode.HTML)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
'''
    with open(os.path.join(server_path, 'bot.py'), 'w') as f: f.write(bot_code)
    SERVERS[bot_name] = {
        'process': None, 'cmd': 'python3 bot.py', 'cwd': '',
        'logs': [f">>> [FX HOSTING] Telegram bot '{bot_name}' created"], 'auto_restart': True,
        'restart_interval': '1h', 'last_start_time': 0, 'status': 'stopped', 'path': server_path,
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'notes': f'Token: {bot_token[:10]}...',
        'group': 'Telegram Bots', 'tags': ['telegram', 'bot'], 'env_vars': {}
    }
    save_servers()
    log_activity("Telegram Bot", f"Deployed bot '{bot_name}'", "admin")
    return jsonify({'status': 'ok', 'server_id': bot_name})

# =============================================================================
# ROLE INFO API
# =============================================================================

@app.route('/api/whoami')
@login_required
def whoami():
    return jsonify({
        'role': 'admin',
        'username': session.get('username', 'unknown'),
        'is_admin': True,
        'login_time': session.get('login_time', 0),
        'permissions': {
            'view_servers': True,
            'view_logs': True,
            'view_stats': True,
            'start_stop_servers': True,
            'manage_files': True,
            'terminal': True,
            'settings': True,
            'backup': True,
            'packages': True,
            'delete_servers': True,
        }
    })

# =============================================================================
# MULTI-USER MANAGEMENT API (ADMIN ONLY)
# =============================================================================

@app.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    safe_users = {}
    for uid, u in USERS.items():
        safe_users[uid] = {
            'username': u.get('username'), 'role': u.get('role'),
            'created_at': u.get('created_at'), 'is_builtin': u.get('is_builtin', False)
        }
    return jsonify({'users': safe_users})

@app.route('/api/users/create', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json() or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role = 'admin'  # Single-role system: every account is ADMIN MODE
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    for u in USERS.values():
        if u.get('username', '').lower() == username.lower():
            return jsonify({'error': 'Username already exists'}), 400
    uid = f"u_{secrets.token_hex(6)}"
    USERS[uid] = {
        'username': username,
        'password_hash': hashlib.sha256(password.encode()).hexdigest(),
        'role': role,
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'is_builtin': False
    }
    save_users(USERS)
    log_activity("User Create", f"Created {role} user '{username}'", "admin")
    return jsonify({'status': 'ok', 'user_id': uid})

@app.route('/api/users/<user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id not in USERS:
        return jsonify({'error': 'User not found'}), 404
    if USERS[user_id].get('is_builtin'):
        return jsonify({'error': 'Cannot delete built-in user'}), 400
    username = USERS[user_id].get('username')
    del USERS[user_id]
    save_users(USERS)
    log_activity("User Delete", f"Deleted user '{username}'", "admin")
    return jsonify({'status': 'ok'})

@app.route('/api/users/<user_id>/password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    if user_id not in USERS:
        return jsonify({'error': 'User not found'}), 404
    data = request.get_json() or request.form
    new_pass = data.get('password', '').strip()
    if len(new_pass) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    USERS[user_id]['password_hash'] = hashlib.sha256(new_pass.encode()).hexdigest()
    save_users(USERS)
    log_activity("User Password Reset", f"Reset password for '{USERS[user_id].get('username')}'", "admin")
    return jsonify({'status': 'ok'})

# =============================================================================
# DOMAIN / SUBDOMAIN MAPPING API
# =============================================================================

@app.route('/api/domains', methods=['GET'])
@login_required
def list_domains():
    return jsonify({'domains': DOMAINS})

@app.route('/api/domains/<server_id>', methods=['POST'])
@admin_required
def set_domain(server_id):
    if server_id not in SERVERS:
        return jsonify({'error': 'Server not found'}), 404
    data = request.get_json() or request.form
    domain = data.get('domain', '').strip().lower()
    port = data.get('port', '').strip()
    ssl = data.get('ssl', False)
    if not domain:
        return jsonify({'error': 'Domain required'}), 400
    if not re.match(r'^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$', domain):
        return jsonify({'error': 'Invalid domain format'}), 400
    if not port.isdigit():
        return jsonify({'error': 'Port must be a number'}), 400
    DOMAINS[server_id] = {
        'domain': domain, 'port': int(port), 'ssl': bool(ssl),
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    save_domains(DOMAINS)
    log_activity("Domain Map", f"Mapped '{domain}' -> '{server_id}:{port}'", "admin")
    return jsonify({'status': 'ok', 'nginx_config': generate_nginx_config(domain, int(port), bool(ssl))})

@app.route('/api/domains/<server_id>/delete', methods=['POST'])
@admin_required
def delete_domain(server_id):
    if server_id in DOMAINS:
        del DOMAINS[server_id]
        save_domains(DOMAINS)
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Domain mapping not found'}), 404

def generate_nginx_config(domain, port, ssl=False):
    if ssl:
        return f"""server {{
    listen 80;
    server_name {domain};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {domain};

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}

# To enable SSL run: certbot --nginx -d {domain}"""
    return f"""server {{
    listen 80;
    server_name {domain};

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}

# To enable SSL run: certbot --nginx -d {domain}"""

@app.route('/api/domains/<server_id>/nginx_config')
@admin_required
def get_nginx_config(server_id):
    if server_id not in DOMAINS:
        return jsonify({'error': 'No domain mapped'}), 404
    d = DOMAINS[server_id]
    return jsonify({'config': generate_nginx_config(d['domain'], d['port'], d.get('ssl', False))})

# =============================================================================
# SERVER HEALTH SCORE API
# =============================================================================

@app.route('/api/health/<server_id>')
@login_required
def get_health(server_id):
    if server_id not in SERVERS:
        return jsonify({'error': 'Server not found'}), 404
    return jsonify(compute_health_score(server_id))

@app.route('/api/health/all')
@login_required
def get_all_health():
    result = {}
    for sid in SERVERS:
        result[sid] = compute_health_score(sid)
    return jsonify({'health': result})

# =============================================================================
# RESOURCE HISTORY API (per-server CPU/RAM graphs)
# =============================================================================

@app.route('/api/resource_history/<server_id>')
@login_required
def get_resource_history(server_id):
    return jsonify({'history': RESOURCE_HISTORY.get(server_id, [])})

# =============================================================================
# WEBHOOK SETTINGS API (ADMIN ONLY)
# =============================================================================

@app.route('/api/webhooks', methods=['GET'])
@admin_required
def get_webhooks():
    wh = CONFIG.get('webhooks', {}).copy()
    # Mask tokens partially for display safety
    if wh.get('discord_url'):
        wh['discord_url_masked'] = wh['discord_url'][:40] + '...' if len(wh['discord_url']) > 40 else wh['discord_url']
    return jsonify(wh)

@app.route('/api/webhooks', methods=['POST'])
@admin_required
def update_webhooks():
    global CONFIG
    data = request.get_json() or request.form
    wh = CONFIG.setdefault('webhooks', {})
    for key in ['discord_url', 'telegram_bot_token', 'telegram_chat_id']:
        if key in data:
            wh[key] = data.get(key, '').strip()
    for key in ['notify_on_crash', 'notify_on_start', 'notify_on_stop', 'notify_on_high_cpu']:
        if key in data:
            wh[key] = data.get(key) in (True, 'true', 'True', 1, '1')
    for key in ['cpu_alert_threshold', 'ram_alert_threshold']:
        if key in data:
            try: wh[key] = int(data.get(key))
            except: pass
    save_json(CONFIG_FILE, CONFIG)
    log_activity("Webhook Settings", "Webhook configuration updated", "admin")
    return jsonify({'status': 'ok'})

@app.route('/api/webhooks/test', methods=['POST'])
@admin_required
def test_webhook():
    data = request.get_json() or request.form
    wh_type = data.get('type', 'discord')
    if wh_type == 'discord':
        send_discord_webhook("🧪 Test Notification", "This is a test message from FX HOSTING Panel. Your Discord webhook is working!", 0x00ff00)
    else:
        send_telegram_webhook("🧪 Test Notification\n\nThis is a test message from FX HOSTING Panel. Your Telegram webhook is working!")
    return jsonify({'status': 'ok', 'message': f'{wh_type} test notification sent'})

# =============================================================================
# STATIC FILES & ERRORS
# =============================================================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    try: return send_file(os.path.join(STATIC_FOLDER, filename))
    except: return "File not found", 404

# =============================================================================
# JINJA-RENDERED EXTERNAL SCRIPT (avoids HTML '</' raw-text termination glitch)
# =============================================================================
@app.route('/app.js')
@login_required
def serve_appjs():
    """Renders static/app.js through Jinja so {{ }} placeholders resolve."""
    from flask import make_response
    try:
        with open(os.path.join(STATIC_FOLDER, 'app.js')) as _f:
            js_src = _f.read()
        js = render_template_string(js_src, **_index_context())
        resp = make_response(js)
        resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        resp.headers['Cache-Control'] = 'no-store'
        return resp
    except Exception:
        import traceback
        traceback.print_exc()
        return "/* app.js render error */", 500

def _index_context():
    """Builds the exact context the index page (and app.js) needs."""
    stats = get_system_stats()
    current_theme = THEMES.get(CONFIG.get('theme', 'pearl'), THEMES['pearl'])
    serializable_servers = {}
    for sid, s in SERVERS.items():
        serializable_servers[sid] = {
            'cmd': s.get('cmd', ''), 'cwd': s.get('cwd', ''),
            'auto_restart': s.get('auto_restart', False),
            'restart_interval': s.get('restart_interval', '1h'),
            'status': s.get('status', 'stopped'), 'path': s.get('path', ''),
            'last_start_time': s.get('last_start_time', 0),
            'created_at': s.get('created_at', 'Unknown'),
            'notes': s.get('notes', ''), 'group': s.get('group', 'default'),
            'tags': s.get('tags', []),
            'uptime': format_uptime(int(time.time() - s.get('last_start_time', 0))) if s.get('status') == 'running' else '0m',
            'pid': s['process'].pid if s.get('process') else None
        }
    return dict(
        base_dir=BASE_DIR, config=CONFIG, theme=current_theme,
        servers=serializable_servers, themes=THEMES,
        stats=stats, app_uptime=format_uptime(int(time.time() - START_TIME)),
        start_date=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(START_TIME)),
        g=None,
    )

@app.errorhandler(404)
def not_found(e): return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    try:
        import traceback
        tb = traceback.format_exception(type(e), e, e.__traceback__)
        with open('error.log', 'a') as _f:
            _f.write(''.join(tb) + '\n')
    except Exception:
        pass
    return jsonify({'error': 'Internal server error'}), 500

# =============================================================================
# JWT FACTORY — panel-এর ভেতরেই JWT token generation + schedule
# (সব কিছু app.py তেই মার্জ করা: jwt_factory + routes + env patch)
import uuid as _uuid
import concurrent.futures as _cf
try:
    from apscheduler.schedulers.background import BackgroundScheduler as _BGS
except ImportError:
    _BGS = None

JWT_API_URL = (os.environ.get('JWT_API_URL') or 'https://fiddu-jwt-olive.vercel.app/token').strip()
JWT_API_KEY = (os.environ.get('JWT_API_KEY') or 'fxfuhx-secret-key').strip()

def _jwf_api_creds():
    """JWT token-generation API endpoint + key — read live from CONFIG so a
    change made in Settings takes effect immediately, no restart needed.
    Key is genuinely optional: leave it blank in Settings if your API
    doesn't need one — an empty key is never sent as a request param."""
    url = (CONFIG.get('jwt_api_url') or JWT_API_URL).strip()
    key = (CONFIG.get('jwt_api_key') or '').strip()
    return url, key

JWF_MAX_WORKERS = 8
JWF_MAX_SOURCE_BYTES = 5 * 1024 * 1024  # 5 MB
JWF_RUNS = {}
JWF_SCHED_FILE = os.path.join(BASE_DIR, 'jwtfactory_schedules.json')
_jwf_lock = threading.Lock()

try:
    with open(JWF_SCHED_FILE, 'r') as _f:
        JWF_SCHEDULES = json.load(_f)
except Exception:
    JWF_SCHEDULES = {}

_jwf_scheduler = None


def _jwf_save_schedules():
    try:
        tmp = JWF_SCHED_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(JWF_SCHEDULES, f, indent=2)
        os.replace(tmp, JWF_SCHED_FILE)
    except Exception as e:
        print('[JWTFactory] schedule save failed:', e)


def _jwf_init_scheduler():
    global _jwf_scheduler
    if _BGS is None:
        print('[JWTFactory] APScheduler missing — schedule runs disabled (pip install apscheduler)')
        return None
    if _jwf_scheduler is not None:
        return _jwf_scheduler
    try:
        sched = _BGS(daemon=True)
        sched.start()
        for sid, sc in list(JWF_SCHEDULES.items()):
            if sc.get('paused'):
                continue
            interval_hours = float(sc.get('interval_hours', 6))
            sched.add_job(_jwf_run_schedule_job, 'interval', args=[sid],
                          hours=interval_hours, next_run_time=None,
                          id='jwtf_' + sid, replace_existing=True,
                          misfire_grace_time=24 * 3600)
        _jwf_scheduler = sched
        print('[JWTFactory] scheduler ok, %d schedules loaded' % len(JWF_SCHEDULES))
        return sched
    except Exception as e:
        print('[JWTFactory] scheduler init failed:', e)
        return None


def _jwf_parse_source(text):
    """Return list of (uid, password). Supports JSON array, JSON object, uid:pass lines."""
    text = (text or '').strip()
    accounts = []
    if text.startswith('['):
        try:
            data = json.loads(text)
            for item in data:
                if isinstance(item, dict):
                    uid = item.get('uid') or item.get('UID') or item.get('uid_str')
                    pwd = item.get('password') or item.get('Password') or item.get('pass')
                    if uid is not None and pwd is not None:
                        accounts.append((str(uid).strip(), str(pwd).strip()))
            return accounts
        except json.JSONDecodeError:
            pass
    if text.startswith('{'):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for uid, pwd in data.items():
                    if uid is not None and pwd is not None:
                        accounts.append((str(uid).strip(), str(pwd).strip()))
            return accounts
        except json.JSONDecodeError:
            pass
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            uid, _, pwd = line.partition(':')
            if uid.strip() and pwd.strip():
                accounts.append((uid.strip(), pwd.strip()))
    return accounts


def _jwf_fetch_one(uid, password):
    try:
        api_url, api_key = _jwf_api_creds()
        params = {'uid': uid, 'password': password}
        if api_key:
            params['key'] = api_key
        r = requests.get(api_url, params=params, timeout=60)
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, dict) and j.get('token'):
                return {'token': j['token'], 'region': j.get('region') or 'unknown',
                        'uid': uid, 'ok': True}
        return {'uid': uid, 'ok': False, 'reason': 'API failed (HTTP %s)' % r.status_code}
    except requests.RequestException as e:
        return {'uid': uid, 'ok': False, 'reason': str(e)[:80]}


def _jwf_process_accounts(accounts, run_id, region_split, output_name):
    """Background worker: generate tokens + optional region-split files."""
    total = len(accounts)
    JWF_RUNS[run_id]['total'] = total
    results_ok, results_fail, region_map = [], [], {}
    done = 0
    t0 = time.time()
    try:
        with _cf.ThreadPoolExecutor(max_workers=JWF_MAX_WORKERS) as ex:
            futures = {ex.submit(_jwf_fetch_one, uid, pwd): (uid, pwd) for uid, pwd in accounts}
            for fut in _cf.as_completed(futures):
                res = fut.result()
                done += 1
                with _jwf_lock:
                    if res['ok']:
                        results_ok.append(res)
                        reg = (res['region'] or 'unknown').strip()
                        region_map.setdefault(reg, []).append({'token': res['token']})
                    else:
                        results_fail.append(res)
                    JWF_RUNS[run_id].update({
                        'done': done,
                        'success': len(results_ok),
                        'failed': len(results_fail),
                        'status': 'running',
                        'elapsed': round(time.time() - t0, 1),
                        'latest': 'Processing %d/%d' % (done, total),
                    })
    except Exception as e:
        with _jwf_lock:
            JWF_RUNS[run_id]['status'] = 'error'
            JWF_RUNS[run_id]['error'] = str(e)[:200]
        return
    try:
        region_files = {}
        if region_split:
            target = region_split
            for reg, toks in region_map.items():
                safe = re.sub(r'[^A-Za-z0-9_-]', '', reg)[:24] or 'unknown'
                fname = 'accounts_%s.json' % safe
                spec = target.get(safe) or target.get(reg)
                _jwf_save_tokens_file(fname, toks, spec)
                region_files[reg] = fname
        main_spec = region_split.get('__main__') if isinstance(region_split, dict) else None
        if main_spec is None:
            main_spec = {'server_id': None, 'path': '', 'filename': output_name}
        main_spec['filename'] = output_name
        _jwf_save_tokens_file(output_name, results_ok, main_spec)
        with _jwf_lock:
            JWF_RUNS[run_id].update({
                'status': 'done',
                'done': done,
                'success': len(results_ok),
                'failed': len(results_fail),
                'finished': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
                'region_files': region_files,
                'latest': 'Done — %d success, %d failed' % (len(results_ok), len(results_fail)),
            })
    except Exception as e:
        with _jwf_lock:
            JWF_RUNS[run_id].update({
                'status': 'error',
                'error': ('Run exception: ' + str(e))[:300],
                'latest': 'Error — ' + str(e)[:80],
            })
        return


def _jwf_save_tokens_file(filename, tokens, spec):
    """Save token list to the chosen server+path, or local fallback."""
    content = json.dumps(tokens, indent=2)
    ok, note = False, ''
    if spec and spec.get('server_id'):
        sid = spec['server_id']
        subpath = (spec.get('path') or '').strip()
        out_name = (spec.get('filename') or filename).strip()
        try:
            if sid in SERVERS:
                raw = SERVERS[sid]['path']
                base = raw if os.path.isabs(raw) else os.path.join(BASE_DIR, raw)
                _sub = (subpath or '').lstrip('/').rstrip('/')
                if _sub.startswith('user_files/'):
                    _target = os.path.normpath(os.path.join(BASE_DIR, _sub))
                else:
                    _target = os.path.normpath(os.path.join(base, _sub)) if _sub else base
                target_dir = _target
                if os.path.realpath(target_dir).startswith(os.path.realpath(BASE_DIR)):
                    os.makedirs(target_dir, exist_ok=True)
                    with open(os.path.join(target_dir, out_name), 'w') as f:
                        f.write(content)
                    try:
                        log_activity('JWT Factory', 'Saved %s -> %s:%s' % (out_name, sid, subpath), 'admin')
                    except Exception:
                        pass
                    print('[JWTFactory] SAVE OK ->', os.path.join(target_dir, out_name), flush=True)
                    ok, note = True, '%s@%s:%s' % (out_name, sid, subpath)
        except Exception as e:
            print('[JWTFactory] SAVE DEBUG spec=', spec, 'err=', e, flush=True)
            note = 'save failed: %s' % str(e)[:120]
    if not ok:
        try:
            local = os.path.join(os.path.join(BASE_DIR, 'user_files'), filename)
            with open(local, 'w') as f:
                f.write(content)
            note = 'local fallback: %s' % local
            ok = True
        except Exception as e:
            note = 'local save failed: %s' % str(e)[:120]
    return ok, note


def _jwf_start_run(server_id, subpath, source_text, output_name, region_map_cfg):
    """region_map_cfg: list of {region, server_id, path, filename} — optional."""
    sid = server_id
    run_id = 'run_' + _uuid.uuid4().hex[:10]
    accounts = _jwf_parse_source(source_text)
    if not accounts:
        return {'error': 'কোনো valid account (uid:pass) পাওয়া যায়নি'}
    region_cfg = {'__main__': {'server_id': sid, 'path': (subpath or '').strip().lstrip('/'), 'filename': output_name}}
    if region_map_cfg:
        for rc in region_map_cfg:
            key = (rc.get('region') or 'unknown').strip()
            region_cfg[key] = {'server_id': rc.get('server_id') or sid,
                               'path': (rc.get('path') or subpath or '').strip().lstrip('/'),
                               'filename': rc.get('filename') or ('accounts_%s.json' % key)}
    with _jwf_lock:
        JWF_RUNS[run_id] = {
            'run_id': run_id, 'total': 0, 'done': 0, 'success': 0, 'failed': 0,
            'status': 'running', 'started': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
            'server_id': sid, 'subpath': subpath, 'output_name': output_name,
        }
    threading.Thread(target=_jwf_process_accounts, args=(accounts, run_id, region_cfg, output_name), daemon=True).start()
    return {'run_id': run_id, 'total': len(accounts), 'message': 'প্রসেসিং শুরু হয়েছে (%d accounts)' % len(accounts)}


def _jwf_run_schedule_job(sid):
    sc = JWF_SCHEDULES.get(sid)
    if not sc or sc.get('paused'):
        return
    try:
        server_id = sc.get('server_id')
        # source can live on a DIFFERENT server/account than the upload target —
        # fall back to server_id for schedules saved before source_server_id existed
        src_server_id = sc.get('source_server_id') or server_id
        subpath = (sc.get('path') or '').strip().lstrip('/')
        out_name = (sc.get('output_name') or 'token_bd.json').strip()
        if server_id not in SERVERS or src_server_id not in SERVERS:
            return
        src_base = SERVERS[src_server_id]['path']
        src_path = os.path.normpath(os.path.join(src_base, (sc.get('source_path') or ''), sc.get('source_file') or ''))
        if not os.path.realpath(src_path).startswith(os.path.realpath(src_base)):
            return
        if not os.path.isfile(src_path):
            return
        with open(src_path, encoding='utf-8', errors='ignore') as f:
            text = f.read()
        if len(text) > JWF_MAX_SOURCE_BYTES:
            text = text[:JWF_MAX_SOURCE_BYTES]
        res = _jwf_start_run(server_id, subpath, text, out_name, sc.get('regions'))
        sc['last_run'] = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        sc['last_run_id'] = res.get('run_id', '')
        # keep next_run in sync with the actual next APScheduler firing —
        # without this it stayed frozen at its very first value forever
        _jwf_sync_next_run(sid)
        _jwf_save_schedules()
    except Exception as e:
        print('[JWTFactory] schedule job error:', e)


def _jwf_sync_next_run(sid):
    """Pull the live next-fire time from APScheduler (authoritative) into the
    schedule record, falling back to an interval-based estimate if the
    scheduler/job isn't available yet."""
    sc = JWF_SCHEDULES.get(sid)
    if not sc:
        return
    if sc.get('paused'):
        sc['next_run'] = 'Paused'
        sc['next_run_ts'] = None
        return
    job = None
    if _jwf_scheduler:
        try:
            job = _jwf_scheduler.get_job('jwtf_' + sid)
        except Exception:
            job = None
    if job and job.next_run_time:
        ts = job.next_run_time.timestamp()
    else:
        ts = datetime.datetime.utcnow().timestamp() + float(sc.get('interval_hours', 6)) * 3600
    sc['next_run_ts'] = ts
    sc['next_run'] = datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M UTC')


def _jwf_source_account_count(sc):
    """How many uid:pass accounts are in this schedule's current source file
    (for the monitor dashboard) — None if the file can't be read right now."""
    try:
        server_id = sc.get('server_id')
        src_server_id = sc.get('source_server_id') or server_id
        if src_server_id not in SERVERS:
            return None
        src_base = SERVERS[src_server_id]['path']
        src_path = os.path.normpath(os.path.join(src_base, (sc.get('source_path') or ''), sc.get('source_file') or ''))
        if not os.path.realpath(src_path).startswith(os.path.realpath(src_base)):
            return None
        if not os.path.isfile(src_path):
            return None
        with open(src_path, encoding='utf-8', errors='ignore') as f:
            text = f.read(JWF_MAX_SOURCE_BYTES)
        return len(_jwf_parse_source(text))
    except Exception:
        return None


def _jwf_list_schedules():
    rows = []
    for sid, sc in JWF_SCHEDULES.items():
        _jwf_sync_next_run(sid)  # always show the true live countdown, not a stale snapshot
        last_run_info = JWF_RUNS.get(sc.get('last_run_id') or '')
        rows.append({
            'id': sid,
            'name': sc.get('name', ''),
            'source_file': sc.get('source_file'),
            'source_path': sc.get('source_path', ''),
            'source_server_id': sc.get('source_server_id') or sc.get('server_id'),
            'server_id': sc.get('server_id'),
            'path': sc.get('path', ''),
            'output_name': sc.get('output_name', 'token_bd.json'),
            'interval_hours': float(sc.get('interval_hours', 6)),
            'paused': bool(sc.get('paused')),
            'last_run': sc.get('last_run'),
            'last_run_stats': sc.get('last_run_stats'),
            'last_run_info': {
                'run_id': sc.get('last_run_id'),
                'status': last_run_info.get('status'),
                'total': last_run_info.get('total'),
                'done': last_run_info.get('done'),
                'success': last_run_info.get('success'),
                'failed': last_run_info.get('failed'),
                'latest': last_run_info.get('latest'),
                'started': last_run_info.get('started'),
                'finished': last_run_info.get('finished'),
            } if last_run_info else None,
            'next_run': sc.get('next_run'),
            'next_run_ts': sc.get('next_run_ts'),
            'account_count': _jwf_source_account_count(sc),
        })
    return rows


def _jwf_create_schedule(data):
    sid = 'sc_' + _uuid.uuid4().hex[:8]
    sc = {
        'name': (data.get('name') or 'Schedule %s' % sid).strip(),
        'source_file': (data.get('source_file') or '').strip(),
        'source_path': (data.get('source_path') or '').strip(),
        'source_server_id': (data.get('source_server_id') or data.get('server_id') or '').strip(),
        'server_id': data.get('server_id', ''),
        'path': (data.get('path') or '').strip(),
        'output_name': (data.get('output_name') or 'token_bd.json').strip(),
        'interval_hours': float(data.get('interval_hours', 6)),
        'paused': False,
        'regions': data.get('regions') or [],
    }
    if not sc['server_id'] or not sc['source_file']:
        return {'error': 'server_id ও source_file দরকার'}
    JWF_SCHEDULES[sid] = sc
    _jwf_save_schedules()
    _jwf_reschedule(sid)
    return {'id': sid, 'name': sc['name']}


def _jwf_update_schedule(sid, data):
    sc = JWF_SCHEDULES.get(sid)
    if not sc:
        return {'error': 'Schedule নেই'}
    for key in ('name', 'source_file', 'source_path', 'source_server_id', 'server_id', 'path',
                'output_name', 'interval_hours', 'paused', 'regions'):
        if key in data:
            sc[key] = data[key]
    _jwf_save_schedules()
    _jwf_reschedule(sid)
    return {'ok': True}


def _jwf_delete_schedule(sid):
    JWF_SCHEDULES.pop(sid, None)
    _jwf_save_schedules()
    if _jwf_scheduler:
        try:
            _jwf_scheduler.remove_job('jwtf_' + sid)
        except Exception:
            pass
    return {'ok': True}


def _jwf_reschedule(sid):
    sched = _jwf_init_scheduler()
    sc = JWF_SCHEDULES.get(sid)
    if not sched or not sc:
        return
    try:
        sched.remove_job('jwtf_' + sid)
    except Exception:
        pass
    if not sc.get('paused'):
        sched.add_job(_jwf_run_schedule_job, 'interval', args=[sid],
                      hours=float(sc.get('interval_hours', 6)), id='jwtf_' + sid,
                      replace_existing=True, misfire_grace_time=24 * 3600)
    _jwf_sync_next_run(sid)
    _jwf_save_schedules()


def _jwf_schedule_action(sid, action):
    sc = JWF_SCHEDULES.get(sid)
    if not sc:
        return {'error': 'Schedule নেই'}
    if action == 'run':
        _jwf_run_schedule_job(sid)
        return {'ok': True, 'message': 'এখনই রান শুরু', 'run_id': sc.get('last_run_id', '')}
    if action == 'pause':
        sc['paused'] = True
        _jwf_reschedule(sid)
        return {'ok': True}
    if action == 'resume':
        sc['paused'] = False
        _jwf_reschedule(sid)
        return {'ok': True}
    return {'error': 'Unknown action'}


# JWT Factory API routes (register_jwt_factory -> inlined)
@app.route('/api/jwtfactory/run', methods=['POST'])
def jwf_run():
    data = request.get_json(force=True, silent=True) or {}
    res = _jwf_start_run(
        server_id=data.get('server_id', ''),
        subpath=(data.get('path') or '').strip(),
        source_text=data.get('source') or '',
        output_name=(data.get('output_name') or 'jwt_token.json').strip(),
        region_map_cfg=data.get('regions'),
    )
    if 'error' in res:
        return jsonify(res), 400
    return jsonify(res)


@app.route('/api/jwtfactory/progress/<run_id>')
def jwf_progress(run_id):
    r = JWF_RUNS.get(run_id)
    if not r:
        return jsonify({'error': 'run not found'}), 404
    if r.get('status') == 'running' and r.get('started'):
        try:
            _st = datetime.datetime.strptime(r['started'], '%Y-%m-%d %H:%M UTC')
            if (datetime.datetime.utcnow() - _st).total_seconds() > 300:
                r['status'] = 'error'
                r['latest'] = 'Run stuck (timed out) — আবার Process Now চাপুন'
        except Exception:
            pass
    return jsonify(r)


@app.route('/api/jwtfactory/runs')
def jwf_runs():
    return jsonify({'runs': list(JWF_RUNS.values())[-20:]})


@app.route('/api/jwtfactory/schedules')
def jwf_list_schedules_route():
    return jsonify({'schedules': _jwf_list_schedules()})


@app.route('/api/jwtfactory/schedules', methods=['POST'])
def jwf_create_schedule_route():
    data = request.get_json(force=True, silent=True) or {}
    res = _jwf_create_schedule(data)
    return (jsonify(res), 400) if 'error' in res else jsonify(res)


@app.route('/api/jwtfactory/schedules/<sid>', methods=['PUT'])
def jwf_update_schedule_route(sid):
    data = request.get_json(force=True, silent=True) or {}
    res = _jwf_update_schedule(sid, data)
    return (jsonify(res), 400) if 'error' in res else jsonify(res)


@app.route('/api/jwtfactory/schedules/<sid>', methods=['DELETE'])
def jwf_delete_schedule_route(sid):
    return jsonify(_jwf_delete_schedule(sid))


@app.route('/api/jwtfactory/schedules/<sid>/action', methods=['POST'])
def jwf_schedule_action_route(sid):
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(_jwf_schedule_action(sid, data.get('action', '')))


# Scheduler lazy-init on first request (Flask 3 removed before_first_request)
_jwf_init_done = {'v': False}


def _jwf_lazy_init():
    if not _jwf_init_done['v']:
        _jwf_init_done['v'] = True
        _jwf_init_scheduler()


@app.before_request
def _jwf_before_request():
    _jwf_lazy_init()


@app.route('/_jwf_init')
def _jwf_init():
    _jwf_init_scheduler()
    return jsonify({'ok': True})

# MAIN
# =============================================================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║   FX HOSTING v4.0.0 - ADMIN MODE                        ║
    ║   Full access for every logged-in account                ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    print(f"[FX HOSTING] Server started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("[FX HOSTING] Panel running on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
