# -*- coding: utf-8 -*-
import datetime
import json
import os
import re
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _split_env_list(raw):
    if not raw:
        return []
    return [part.strip() for part in re.split(r'[\n,;]+', str(raw)) if part.strip()]


def _parse_targets_from_env():
    targets = {}

    discord_url = (os.getenv('WEBHOOK_DISCORD_URL') or '').strip()
    if discord_url:
        targets['discord'] = discord_url

    slack_url = (os.getenv('WEBHOOK_SLACK_URL') or '').strip()
    if slack_url:
        targets['slack'] = slack_url

    telegram_url = (os.getenv('WEBHOOK_TELEGRAM_URL') or '').strip()
    if telegram_url:
        targets['telegram'] = telegram_url
    else:
        telegram_bot_token = (os.getenv('WEBHOOK_TELEGRAM_BOT_TOKEN') or '').strip()
        if telegram_bot_token:
            targets['telegram'] = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"

    generic = os.getenv('WEBHOOK_NOTIFY_URLS') or ''
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
        chat_id = (os.getenv('WEBHOOK_TELEGRAM_CHAT_ID') or '').strip()
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
        timeout = float(os.getenv('WEBHOOK_NOTIFY_TIMEOUT', '5'))
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
