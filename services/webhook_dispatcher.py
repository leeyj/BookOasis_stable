# -*- coding: utf-8 -*-
import datetime
import hashlib
import hmac
import json
import os
import re
import urllib.request
from services.settings_service import SettingsService

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get_setting_or_env(key, default=''):
    try:
        value = SettingsService.get(key, '', db_type='general')
        if str(value).strip() != '':
            return str(value)
    except Exception:
        pass
    return str(os.getenv(key, default) or '')


def _split_env_list(raw):
    if not raw:
        return []
    return [part.strip() for part in re.split(r'[\n,;]+', str(raw)) if part.strip()]


def _parse_targets_from_env():
    targets = {}

    discord_url = _get_setting_or_env('WEBHOOK_DISCORD_URL').strip()
    if discord_url:
        targets['discord'] = discord_url

    slack_url = _get_setting_or_env('WEBHOOK_SLACK_URL').strip()
    if slack_url:
        targets['slack'] = slack_url

    telegram_url = _get_setting_or_env('WEBHOOK_TELEGRAM_URL').strip()
    if telegram_url:
        targets['telegram'] = telegram_url
    else:
        telegram_bot_token = _get_setting_or_env('WEBHOOK_TELEGRAM_BOT_TOKEN').strip()
        if telegram_bot_token:
            targets['telegram'] = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"

    generic = _get_setting_or_env('WEBHOOK_NOTIFY_URLS')
    unnamed_index = 0
    for item in _split_env_list(generic):
        if '=' in item:
            name, url = item.split('=', 1)
            name = name.strip().lower()
            url = url.strip()
        else:
            unnamed_index += 1
            name = f'url{unnamed_index}'
            url = item

        if not url:
            continue
        if not (url.startswith('http://') or url.startswith('https://')):
            continue
        targets[name] = url

    return targets


def _build_channel_payload(channel, event, payload):
    title = f"[BookOasis] {event}"
    compact = json.dumps(payload or {}, ensure_ascii=False)

    if channel == 'discord':
        return {
            'username': 'BookOasis',
            'content': f"{title}\n{compact[:1700]}"
        }

    if channel == 'slack':
        return {
            'text': f"{title}\n{compact[:3000]}"
        }

    if channel == 'telegram':
        body = {
            'text': f"{title}\n{compact[:3500]}",
            'disable_web_page_preview': True,
        }
        chat_id = _get_setting_or_env('WEBHOOK_TELEGRAM_CHAT_ID').strip()
        if chat_id:
            body['chat_id'] = chat_id
        return body

    return {
        'source': 'bookoasis',
        'event': event,
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'payload': payload or {},
    }


def dispatch_webhook_event(event, payload=None, channels=None):
    targets = _parse_targets_from_env()
    if not targets:
        return {'success': False, 'sent': 0, 'failed': 0, 'error': 'no webhook targets configured'}

    selected = {}
    if channels:
        wanted = {str(ch).strip().lower() for ch in channels if str(ch).strip()}
        for name, url in targets.items():
            if name in wanted:
                selected[name] = url
    else:
        selected = dict(targets)

    if not selected:
        return {'success': False, 'sent': 0, 'failed': 0, 'error': 'no matched webhook channels'}

    try:
        timeout = float(_get_setting_or_env('WEBHOOK_NOTIFY_TIMEOUT', '5'))
    except Exception:
        timeout = 5.0
    sent = 0
    failed = 0
    errors = []

    for channel, url in selected.items():
        body = _build_channel_payload(channel, event, payload)
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = getattr(resp, 'status', 200)
                if code < 200 or code >= 300:
                    failed += 1
                    errors.append(f"{channel}: HTTP {code}")
                else:
                    sent += 1
        except Exception as exc:
            failed += 1
            errors.append(f"{channel}: {exc}")

    return {
        'success': failed == 0,
        'sent': sent,
        'failed': failed,
        'errors': errors,
        'targets': list(selected.keys()),
    }


def _parse_event_endpoints():
    """Parse standard event endpoints from env var (comma/newline/semicolon separated)."""
    raw = _get_setting_or_env('WEBHOOK_EVENT_ENDPOINTS') or _get_setting_or_env('WEBHOOK_EVENT_ENDPOINT') or ''
    endpoints = []
    for item in _split_env_list(raw):
        if item.startswith('http://') or item.startswith('https://'):
            endpoints.append(item)
    return list(dict.fromkeys(endpoints))


def _sign_payload(secret, body_text):
    if not secret:
        return None
    digest = hmac.new(secret.encode('utf-8'), body_text.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _default_system_account():
    return {
        'id': 0,
        'title': 'system',
    }


def _to_unix_timestamp(dt_text):
    if not dt_text:
        return None
    text = str(dt_text).strip()
    if not text:
        return None

    # Common sqlite format in this project: YYYY-MM-DD HH:MM:SS
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            dt = datetime.datetime.strptime(text, fmt)
            return int(dt.timestamp())
        except Exception:
            pass

    try:
        return int(float(text))
    except Exception:
        return None


def build_book_event_payload(event, account=None, metadata=None, user=True):
    """Build normalized webhook event payload for book lifecycle/read events."""
    safe_event = str(event or '').strip()
    if not safe_event:
        safe_event = 'book.read'

    payload = {
        'event': safe_event,
        'user': bool(user),
        'Account': account or _default_system_account(),
        'Metadata': metadata or {},
    }
    return payload


def dispatch_standard_book_event(payload, endpoints=None):
    """Dispatch standardized book event payload to community webhook endpoint(s)."""
    selected = list(dict.fromkeys(endpoints or _parse_event_endpoints()))
    if not selected:
        return {
            'success': False,
            'sent': 0,
            'failed': 0,
            'error': 'no standard event webhook endpoint configured',
        }

    try:
        timeout = float(_get_setting_or_env('WEBHOOK_EVENT_TIMEOUT', _get_setting_or_env('WEBHOOK_NOTIFY_TIMEOUT', '5')))
    except Exception:
        timeout = 5.0

    try:
        retries = int(_get_setting_or_env('WEBHOOK_EVENT_RETRY', '2'))
    except Exception:
        retries = 2
    retries = max(0, min(5, retries))

    secret = _get_setting_or_env('WEBHOOK_EVENT_SECRET').strip()
    body_text = json.dumps(payload or {}, ensure_ascii=False)
    sent = 0
    failed = 0
    errors = []

    for endpoint in selected:
        ok = False
        last_err = None
        for attempt in range(1, retries + 2):
            headers = {
                'Content-Type': 'application/json',
                'X-BookOasis-Event': str((payload or {}).get('event') or ''),
            }
            signature = _sign_payload(secret, body_text)
            if signature:
                headers['X-BookOasis-Signature'] = signature

            req = urllib.request.Request(
                endpoint,
                data=body_text.encode('utf-8'),
                headers=headers,
                method='POST',
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    code = getattr(resp, 'status', 200)
                    if 200 <= code < 300:
                        sent += 1
                        ok = True
                        break
                    last_err = f"HTTP {code}"
            except Exception as exc:
                last_err = str(exc)

        if not ok:
            failed += 1
            errors.append(f"{endpoint}: {last_err or 'request failed'}")

    return {
        'success': failed == 0,
        'sent': sent,
        'failed': failed,
        'errors': errors,
        'targets': selected,
    }
