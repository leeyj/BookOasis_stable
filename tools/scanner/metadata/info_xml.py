# -*- coding: utf-8 -*-
import html
import os
import re
import threading
import time
import xml.etree.ElementTree as ET

TARGET_FILENAME = 'info.xml'

HTML_TAG_RE = re.compile(r'<[^>]*>')
HANGUL_CONSONANTS = set(['ㄱ','ㄴ','ㄷ','ㄹ','ㅁ','ㅂ','ㅅ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ',
                         '가','나','다','라','마','바','사','아','자','차','카','타','파','하'])


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
    return parse_info_xml(target_path, files=files, is_remote=is_remote)


def parse_info_xml(folder_path, files=None, is_remote=False):
    xml_path = os.path.join(folder_path, 'info.xml')
    meta = {
        'title': '',
        'series': '',
        'author': '',
        'publisher': '',
        'summary': '',
        'genre': '',
        'tags': '',
        'release_date': ''
    }

    has_xml = False
    if files is not None:
        has_xml = any(f.lower() == 'info.xml' for f in files)
    else:
        has_xml = os.path.exists(xml_path)

    if not has_xml:
        return meta

    try:
        content = read_file_with_timeout(xml_path, is_remote)
        if content is None:
            return meta

        root = ET.fromstring(content.encode('utf-8'))

        def _get_text(tag):
            elem = root.find(tag)
            return elem.text.strip() if elem is not None and elem.text else ''

        meta['title'] = _get_text('Title')
        meta['series'] = _get_text('Series')
        meta['author'] = _get_text('Writer')
        meta['publisher'] = _get_text('Publisher')
        meta['summary'] = _get_text('Summary')
        meta['genre'] = _get_text('Genre')
        meta['tags'] = _get_text('Tags')

        year = _get_text('Year')
        month = _get_text('Month').zfill(2) if _get_text('Month') else ''
        day = _get_text('Day').zfill(2) if _get_text('Day') else ''

        if year:
            meta['release_date'] = f"{year}-{month or '01'}-{day or '01'}"
    except Exception as e:
        print(f"[Scanner] XML parsing error ({folder_path}): {e}")

    meta['summary'] = clean_html_tags(meta['summary'])
    return meta