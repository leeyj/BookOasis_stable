# -*- coding: utf-8 -*-
"""Per-IP failed-login throttle for header-auth endpoints (OPDS / App OPDS / e-paper Basic auth, kosync).

Only failures are counted, so normal clients that resend credentials on every request are never slowed.
After MAX_FAILURES wrong attempts within WINDOW_SECONDS, the IP gets 429 for BLOCK_SECONDS.

Known limit: behind a reverse proxy every client shares the proxy address, so one attacker can briefly
block feed logins for everyone (already-cached OPDS logins keep working). X-Forwarded-For is not trusted
because any client can forge it. The block is short and logged for that reason.
State lives in memory (single web worker), so a restart clears it.
"""
import threading
import time
from collections import deque

MAX_FAILURES = 10
WINDOW_SECONDS = 300
BLOCK_SECONDS = 300
_MAX_TRACKED = 10000

_lock = threading.Lock()
_failures = {}   # ip -> deque[timestamp]
_blocked = {}    # ip -> unblock timestamp


def _prune(now):
    for ip in [ip for ip, until in _blocked.items() if until <= now]:
        _blocked.pop(ip, None)
    if len(_failures) > _MAX_TRACKED:
        for ip in [ip for ip, q in _failures.items() if not q or q[-1] < now - WINDOW_SECONDS]:
            _failures.pop(ip, None)
        while len(_failures) > _MAX_TRACKED:
            _failures.pop(next(iter(_failures)))


def retry_after(ip, now=None):
    """Seconds left on the block for this IP, 0 when not blocked."""
    if not ip:
        return 0
    now = time.time() if now is None else now
    with _lock:
        until = _blocked.get(ip)
        if until is None:
            return 0
        if until <= now:
            _blocked.pop(ip, None)
            return 0
        return max(1, int(until - now + 0.999))


def record_failure(ip, where='', now=None):
    """Count one wrong attempt. Returns True when this attempt started a block."""
    if not ip:
        return False
    now = time.time() if now is None else now
    with _lock:
        _prune(now)
        q = _failures.setdefault(ip, deque())
        q.append(now)
        while q and q[0] < now - WINDOW_SECONDS:
            q.popleft()
        if len(q) >= MAX_FAILURES and ip not in _blocked:
            _blocked[ip] = now + BLOCK_SECONDS
            q.clear()
            print(f"[AUTH-THROTTLE] blocked ip={ip} for {BLOCK_SECONDS}s after {MAX_FAILURES} failed logins"
                  f" within {WINDOW_SECONDS}s ({where or '-'})")
            return True
    return False


def record_success(ip):
    if not ip:
        return
    with _lock:
        _failures.pop(ip, None)


def reset():
    """Tests only."""
    with _lock:
        _failures.clear()
        _blocked.clear()


def abort_if_blocked(where=''):
    """Inside a Flask request: answer 429 (with Retry-After) when the client IP is blocked."""
    from flask import Response, abort, request
    wait = retry_after(request.remote_addr)
    if wait:
        res = Response('Too many failed logins. Try again later.\n', status=429,
                       mimetype='text/plain; charset=utf-8')
        res.headers['Retry-After'] = str(wait)
        res.headers['Cache-Control'] = 'no-store'
        abort(res)


def note_result(ok, where=''):
    """Inside a Flask request: record the outcome of a credential check for the client IP."""
    from flask import request
    if ok:
        record_success(request.remote_addr)
    else:
        record_failure(request.remote_addr, where=f"{where} {request.path}".strip())
