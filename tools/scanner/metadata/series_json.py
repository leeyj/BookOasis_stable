# -*- coding: utf-8 -*-
import json
import os
import html
import re
import threading
import time

TARGET_FILENAME = 'series.json'

HTML_TAG_RE = re.compile(r'<[^>]*>')


class NetworkCircuitBreaker:
    def __init__(self, max_failures=3, reset_timeout=60):
        self.failures = 0
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self._lock = threading.Lock()

    def is_tripped(self):
        with self._lock:
            if self.failures >= self.max_failures:
                if time.time() - self.last_failure_time > self.reset_timeout:
                    self.failures = 0
                    return False
                return True
            return False

    def record_failure(self):
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()

    def record_success(self):
        with self._lock:
            if self.failures > 0:
                self.failures = 0


_circuit_breaker = NetworkCircuitBreaker(max_failures=3, reset_timeout=60)


def clean_html_tags(text):
    if not text:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p\s*>', '', text, flags=re.IGNORECASE)
    cleaned = HTML_TAG_RE.sub('', text)
    return html.unescape(cleaned).strip()


def read_file_with_timeout(file_path, is_remote, timeout=10):
    if not is_remote:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return None

    if _circuit_breaker.is_tripped():
        return None

    result = []

    def _read():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                result.append(f.read())
        except Exception as e:
            result.append(e)

    t = threading.Thread(target=_read)
    t.daemon = True
    t.start()
    t.join(timeout)

    if t.is_alive():
        _circuit_breaker.record_failure()
        return None

    if not result:
        _circuit_breaker.record_failure()
        return None

    res = result[0]
    if isinstance(res, Exception):
        return None

    _circuit_breaker.record_success()
    return res


def parse(target_path, files=None, is_remote=False):
    return parse_series_json(target_path, files=files, is_remote=is_remote)


def parse_series_json(folder_path, files=None, is_remote=False):
    json_path = os.path.join(folder_path, 'series.json')
    meta = {
        'author': '',
        'summary': '',
        'cover_image_url': '',
        'is_webtoon': False
    }

    has_json = False
    if files is not None:
        has_json = any(f.lower() == 'series.json' for f in files)
    else:
        has_json = os.path.exists(json_path)

    if not has_json:
        return meta

    meta['is_webtoon'] = True

    try:
        content = read_file_with_timeout(json_path, is_remote)
        if content is not None:
            data = json.loads(content)
            if isinstance(data, dict):
                meta['author'] = data.get('author', '')
                meta['summary'] = clean_html_tags(data.get('desc', ''))
                meta['cover_image_url'] = data.get('image', '')
    except Exception as e:
        print(f"[Scanner] JSON parsing error ({folder_path}): {e}")

    return meta