"""jwt_factory.py - JWT Token Factory backend.
Panel-এর ভেতরেই JWT token generation + region split + auto upload + schedule।
Telegram bot-এর dependency নাই — প্যনেল backend (Flask) সব করে।

Endpoints registered here:
  GET  /api/jwtfactory/progress/<run_id>        - live progress
  POST /api/jwtfactory/run                       - process accounts now (or enqueue for a schedule)
  GET  /api/jwtfactory/schedules                 - all schedules + stats
  POST /api/jwtfactory/schedules                 - create schedule
  PUT  /api/jwtfactory/schedules/<sid>           - update schedule
  DELETE /api/jwtfactory/schedules/<sid>         - delete schedule
  POST /api/jwtfactory/schedules/<sid>/action    - run now / pause / resume

Env (Railway Variables, optional):
  JWT_API_URL  - default https://fiddu-jwt-token.vercel.app/token
  JWT_API_KEY  - default fxfuhx-secret-key
"""
import os
import re
import json
import time
import uuid
import threading
import concurrent.futures
from datetime import datetime

import requests

# ---------------------------------------------------------------------------
# Config (env থেকে, default বট-এর default API)
# ---------------------------------------------------------------------------
JWT_API_URL = (os.environ.get('JWT_API_URL') or 'https://fiddu-jwt-token.vercel.app/token').strip()
JWT_API_KEY = (os.environ.get('JWT_API_KEY') or 'fxfuhx-secret-key').strip()

MAX_WORKERS = 8
MAX_SOURCE_BYTES = 5 * 1024 * 1024  # 5 MB

# ---------------------------------------------------------------------------
# In-memory progress + persistent schedules
# ---------------------------------------------------------------------------
RUNS = {}                # run_id -> {total, done, success, failed, status, started, finished, ...}
SCHED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jwtfactory_schedules.json')
_run_lock = threading.Lock()

try:
    with open(SCHED_FILE, 'r') as _f:
        SCHEDULES = json.load(_f)
except Exception:
    SCHEDULES = {}

_scheduler = None


def _save_schedules():
    try:
        tmp = SCHED_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(SCHEDULES, f, indent=2)
        os.replace(tmp, SCHED_FILE)
    except Exception as e:
        print('[JWTFactory] schedule save failed:', e)


def _init_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        sched = BackgroundScheduler(daemon=True)
        sched.start()
        for sid, sc in list(SCHEDULES.items()):
            if sc.get('paused'):
                continue
            interval_hours = float(sc.get('interval_hours', 6))
            sched.add_job(_run_schedule_job, 'interval', args=[sid],
                          hours=interval_hours, next_run_time=None,
                          id='jwtf_' + sid, replace_existing=True,
                          misfire_grace_time=24 * 3600)
        _scheduler = sched
        print('[JWTFactory] scheduler ok, %d schedules loaded' % len(SCHEDULES))
        return sched
    except ImportError:
        print('[JWTFactory] APScheduler missing — schedule runs disabled (pip install apscheduler)')
        return None


# ---------------------------------------------------------------------------
# Parsing helpers (same formats as the bot)
# ---------------------------------------------------------------------------
def _parse_source(text):
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


# ---------------------------------------------------------------------------
# Single-account token fetch
# ---------------------------------------------------------------------------
def _fetch_one(uid, password):
    try:
        r = requests.get(JWT_API_URL, params={'uid': uid, 'password': password, 'key': JWT_API_KEY},
                         timeout=60)
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, dict) and j.get('token'):
                return {'token': j['token'], 'region': j.get('region') or 'unknown',
                        'uid': uid, 'ok': True}
        return {'uid': uid, 'ok': False, 'reason': 'API failed (HTTP %s)' % r.status_code}
    except requests.RequestException as e:
        return {'uid': uid, 'ok': False, 'reason': str(e)[:80]}


def _process_accounts(accounts, run_id, region_split):
    """Background worker: generate tokens + optional region-split files."""
    total = len(accounts)
    RUNS[run_id]['total'] = total
    results_ok, results_fail, region_map = [], [], {}
    done = 0
    t0 = time.time()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(_fetch_one, uid, pwd): (uid, pwd) for uid, pwd in accounts}
            for fut in concurrent.futures.as_completed(futures):
                res = fut.result()
                done += 1
                with _run_lock:
                    if res['ok']:
                        results_ok.append(res)
                        reg = (res['region'] or 'unknown').strip()
                        region_map.setdefault(reg, []).append({'token': res['token']})
                    else:
                        results_fail.append(res)
                    RUNS[run_id].update({
                        'done': done,
                        'success': len(results_ok),
                        'failed': len(results_fail),
                        'status': 'running',
                        'elapsed': round(time.time() - t0, 1),
                        'latest': 'Processing %d/%d' % (done, total),
                    })
    except Exception as e:
        with _run_lock:
            RUNS[run_id]['status'] = 'error'
            RUNS[run_id]['error'] = str(e)[:200]
        return

    # Region split -> accounts{Region}.json
    region_files = {}
    if region_split:
        target = region_split  # dict: {region_name: {'server_id':..., 'path':..., 'filename':...}}
        for reg, toks in region_map.items():
            safe = re.sub(r'[^A-Za-z0-9_-]', '', reg)[:24] or 'unknown'
            fname = 'accounts_%s.json' % safe
            spec = target.get(safe) or target.get(reg)
            _save_tokens_file(fname, toks, spec)
            region_files[reg] = fname

    # Main output: use the configured output name (default token_bd.json)
    main_spec = region_split.get('__main__') if isinstance(region_split, dict) else None
    if main_spec is None:
        main_spec = {'server_id': None, 'path': '', 'filename': output_name}
    main_spec['filename'] = output_name
    _save_tokens_file(output_name, results_ok, main_spec)

    with _run_lock:
        RUNS[run_id].update({
            'status': 'done',
            'done': done,
            'success': len(results_ok),
            'failed': len(results_fail),
            'finished': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
            'region_files': region_files,
            'latest': 'Done — %d success, %d failed' % (len(results_ok), len(results_fail)),
        })


def _save_tokens_file(filename, tokens, spec):
    """Save token list to the chosen server+path, or local fallback."""
    content = json.dumps(tokens, indent=2)
    ok, note = False, ''
    if spec and spec.get('server_id'):
        sid = spec['server_id']
        subpath = (spec.get('path') or '').strip()
        out_name = (spec.get('filename') or filename).strip()
        try:
            from app import SERVERS, BASE_DIR, log_activity
            import app as _app
            if sid in SERVERS:
                raw = _app.SERVERS[sid]['path']
                import os as _os
                base = raw if _os.path.isabs(raw) else _os.path.join(_app.BASE_DIR, raw)
                _sub = (subpath or '').lstrip('/').rstrip('/')
                # Path policy: if the path starts with 'user_files/' it is
                # interpreted relative to the PANEL root (BASE_DIR);
                # otherwise it is relative to this server's folder.
                if _sub.startswith('user_files/'):
                    _target = _os.path.normpath(_os.path.join(_app.BASE_DIR, _sub))
                else:
                    _target = _os.path.normpath(_os.path.join(base, _sub)) if _sub else base
                target_dir = _target
                if _os.path.realpath(target_dir).startswith(_os.path.realpath(_app.BASE_DIR)):
                    _os.makedirs(target_dir, exist_ok=True)
                    with open(_os.path.join(target_dir, out_name), 'w') as f:
                        f.write(content)
                    try:
                        log_activity('JWT Factory',
                                     'Saved %s -> %s:%s' % (out_name, sid, subpath), 'admin')
                    except Exception:
                        pass
                    print('[JWTFactory] SAVE OK ->', os.path.join(target_dir, out_name), flush=True)
                    ok, note = True, '%s@%s:%s' % (out_name, sid, subpath)
        except Exception as e:
            _dbg_base = locals().get('base', '?')
            print('[JWTFactory] SAVE DEBUG spec=', spec, 'base=', _dbg_base, 'err=', e, flush=True)
            note = 'save failed: %s' % str(e)[:120]
    if not ok:
        try:
            local = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_files'), filename)
            with open(local, 'w') as f:
                f.write(content)
            note = 'local fallback: %s' % local
            ok = True
        except Exception as e:
            note = 'local save failed: %s' % str(e)[:120]
    return ok, note


# ---------------------------------------------------------------------------
# Run now
# ---------------------------------------------------------------------------
def start_run(server_id, subpath, source_text, output_name, region_map_cfg):
    """region_map_cfg: list of {region, server_id, path, filename} — optional."""
    sid = server_id
    run_id = 'run_' + uuid.uuid4().hex[:10]
    accounts = _parse_source(source_text)
    if not accounts:
        return {'error': 'কোনো valid account (uid:pass) পাওয়া যায়নি'}
    region_cfg = {'__main__': {'server_id': sid, 'path': (subpath or '').strip().lstrip('/'), 'filename': output_name}}
    if region_map_cfg:
        for rc in region_map_cfg:
            key = (rc.get('region') or 'unknown').strip()
            region_cfg[key] = {'server_id': rc.get('server_id') or sid,
                               'path': (rc.get('path') or subpath or '').strip().lstrip('/'),
                               'filename': rc.get('filename') or ('accounts_%s.json' % key)}
    with _run_lock:
        RUNS[run_id] = {
            'run_id': run_id, 'total': 0, 'done': 0, 'success': 0, 'failed': 0,
            'status': 'running', 'started': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
            'server_id': sid, 'subpath': subpath, 'output_name': output_name,
        }
    threading.Thread(target=_process_accounts, args=(accounts, run_id, region_cfg), daemon=True).start()
    return {'run_id': run_id, 'total': len(accounts), 'message': 'প্রসেসিং শুরু হয়েছে (%d accounts)' % len(accounts)}


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------
def _run_schedule_job(sid):
    sc = SCHEDULES.get(sid)
    if not sc or sc.get('paused'):
        return
    try:
        source_file = sc.get('source_file')
        server_id = sc.get('server_id')
        subpath = (sc.get('path') or '').strip().lstrip('/')
        out_name = (sc.get('output_name') or 'token_bd.json').strip()
        from app import SERVERS
        if server_id not in SERVERS:
            return
        base = SERVERS[server_id]['path']
        import os as _os
        src_path = _os.path.normpath(_os.path.join(base, (sc.get('source_path') or ''), source_file))
        if not _os.path.isfile(src_path):
            return
        with open(src_path, encoding='utf-8', errors='ignore') as f:
            text = f.read()
        if len(text) > MAX_SOURCE_BYTES:
            text = text[:MAX_SOURCE_BYTES]
        res = start_run(server_id, subpath, text, out_name, sc.get('regions'))
        sc['last_run'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        sc['last_run_id'] = res.get('run_id', '')
        _save_schedules()
    except Exception as e:
        print('[JWTFactory] schedule job error:', e)


def list_schedules():
    rows = []
    for sid, sc in SCHEDULES.items():
        total = sc.get('last_total') or 0
        rows.append({
            'id': sid,
            'name': sc.get('name', ''),
            'source_file': sc.get('source_file'),
            'server_id': sc.get('server_id'),
            'path': sc.get('path', ''),
            'output_name': sc.get('output_name', 'token_bd.json'),
            'interval_hours': float(sc.get('interval_hours', 6)),
            'paused': bool(sc.get('paused')),
            'last_run': sc.get('last_run'),
            'last_run_stats': sc.get('last_run_stats'),
            'next_run': sc.get('next_run'),
        })
    return rows


def create_schedule(data):
    sid = 'sc_' + uuid.uuid4().hex[:8]
    sc = {
        'name': (data.get('name') or 'Schedule %s' % sid).strip(),
        'source_file': (data.get('source_file') or '').strip(),
        'source_path': (data.get('source_path') or '').strip(),
        'server_id': data.get('server_id', ''),
        'path': (data.get('path') or '').strip(),
        'output_name': (data.get('output_name') or 'token_bd.json').strip(),
        'interval_hours': float(data.get('interval_hours', 6)),
        'paused': False,
        'regions': data.get('regions') or [],
    }
    if not sc['server_id'] or not sc['source_file']:
        return {'error': 'server_id ও source_file দরকার'}
    SCHEDULES[sid] = sc
    _save_schedules()
    _reschedule(sid)
    return {'id': sid, 'name': sc['name']}


def update_schedule(sid, data):
    sc = SCHEDULES.get(sid)
    if not sc:
        return {'error': 'Schedule নেই'}
    for key in ('name', 'source_file', 'source_path', 'server_id', 'path',
                'output_name', 'interval_hours', 'paused', 'regions'):
        if key in data:
            sc[key] = data[key]
    _save_schedules()
    _reschedule(sid)
    return {'ok': True}


def delete_schedule(sid):
    SCHEDULES.pop(sid, None)
    _save_schedules()
    if _scheduler:
        try:
            _scheduler.remove_job('jwtf_' + sid)
        except Exception:
            pass
    return {'ok': True}


def _reschedule(sid):
    sched = _init_scheduler()
    sc = SCHEDULES.get(sid)
    if not sched or not sc:
        return
    try:
        sched.remove_job('jwtf_' + sid)
    except Exception:
        pass
    if not sc.get('paused'):
        sched.add_job(_run_schedule_job, 'interval', args=[sid],
                      hours=float(sc.get('interval_hours', 6)), id='jwtf_' + sid,
                      replace_existing=True, misfire_grace_time=24 * 3600)
        nxt = datetime.utcnow().timestamp() + float(sc.get('interval_hours', 6)) * 3600
        sc['next_run'] = datetime.utcfromtimestamp(nxt).strftime('%Y-%m-%d %H:%M UTC')
    else:
        sc['next_run'] = 'Paused'
    _save_schedules()


def schedule_action(sid, action):
    sc = SCHEDULES.get(sid)
    if not sc:
        return {'error': 'Schedule নেই'}
    if action == 'run':
        _run_schedule_job(sid)
        return {'ok': True, 'message': 'এখনই রান শুরু'}
    if action == 'pause':
        sc['paused'] = True
        _reschedule(sid)
        return {'ok': True}
    if action == 'resume':
        sc['paused'] = False
        _reschedule(sid)
        return {'ok': True}
    return {'error': 'Unknown action'}
