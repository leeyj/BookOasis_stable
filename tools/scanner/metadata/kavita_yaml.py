# -*- coding: utf-8 -*-
import html
import os
import re
import threading
import time

import yaml

TARGET_FILENAME = 'kavita.yaml'

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
    return parse_kavita_yaml(target_path, files=files, is_remote=is_remote)


def parse_kavita_yaml(folder_path, files=None, is_remote=False):
    yaml_path = os.path.join(folder_path, 'kavita.yaml')
    meta = {
        'author': '',
        'isbn': '',
        'publisher': '',
        'summary': '',
        'score': 0,
        'link': '',
        'genre': '',
        'tags': '',
        'cover_b64_map': {},
        'has_yaml': False,
        'parser_warnings': []
    }

    has_yaml = False
    actual_yaml_path = yaml_path

    if files is not None:
        for f in files:
            if f.lower() in ('kavita.yaml', 'kavita.yml'):
                has_yaml = True
                actual_yaml_path = os.path.join(folder_path, f)
                break
    else:
        if os.path.exists(folder_path):
            try:
                for f in os.listdir(folder_path):
                    if f.lower() in ('kavita.yaml', 'kavita.yml'):
                        has_yaml = True
                        actual_yaml_path = os.path.join(folder_path, f)
                        break
            except Exception:
                pass

    if not has_yaml:
        return meta

    meta['has_yaml'] = True

    try:
        from yaml import CSafeLoader as SafeLoader
    except ImportError:
        from yaml import SafeLoader

    try:
        content = read_file_with_timeout(actual_yaml_path, is_remote)
        if content is None:
            return meta

        data = yaml.load(content, Loader=SafeLoader) or {}

        def _parse_list_or_str(val):
            if not val:
                return ''
            if isinstance(val, list):
                return ', '.join(str(v).strip() for v in val if v)
            return str(val).strip()

        def _parse_isbn(val):
            if val is None:
                return ''
            if isinstance(val, list):
                for item in val:
                    text = str(item or '').strip()
                    if text:
                        return text
                return ''
            return str(val).strip()

        if isinstance(data, dict):
            sources = [data.get('meta', {}), data]
            for src in sources:
                if not isinstance(src, dict):
                    continue
                meta['publisher'] = meta['publisher'] or src.get('Person Publisher') or src.get('publisher') or ''
                meta['author'] = meta['author'] or src.get('Person Writers') or src.get('Writer') or src.get('author') or ''
                meta['isbn'] = meta['isbn'] or _parse_isbn(
                    src.get('ISBN') or src.get('Isbn') or src.get('isbn') or src.get('isbn13') or src.get('isbn_13')
                )
                meta['summary'] = meta['summary'] or src.get('Summary') or src.get('summary') or ''
                meta['link'] = meta['link'] or src.get('Web Links') or src.get('link') or ''
                meta['tags'] = meta['tags'] or _parse_list_or_str(src.get('Tags') or src.get('tags') or src.get('tag'))
                meta['genre'] = meta['genre'] or _parse_list_or_str(src.get('Genres') or src.get('genre'))

            search_list = data.get('search', [])
            if search_list and isinstance(search_list, list) and len(search_list) > 0:
                search_item = search_list[0]
                if isinstance(search_item, dict):
                    meta['author'] = meta['author'] or search_item.get('author', '')
                    meta['publisher'] = meta['publisher'] or search_item.get('publisher', '')
                    meta['isbn'] = meta['isbn'] or _parse_isbn(
                        search_item.get('isbn') or search_item.get('isbn13') or search_item.get('isbn_13')
                    )
                    meta['link'] = meta['link'] or search_item.get('link', '')
                    meta['summary'] = meta['summary'] or search_item.get('description', '')
                    meta['score'] = search_item.get('score', meta['score'])
                    meta['tags'] = meta['tags'] or _parse_list_or_str(search_item.get('tag') or search_item.get('tags') or search_item.get('Tags'))
                    meta['genre'] = meta['genre'] or _parse_list_or_str(search_item.get('genre') or search_item.get('genres') or search_item.get('Genres'))

            files_node = data.get('files', {})
            first_cover_b64 = None
            if isinstance(files_node, dict):
                for fname, info in files_node.items():
                    if isinstance(info, dict) and 'cover' in info:
                        cover_val = info['cover']
                        if cover_val and isinstance(cover_val, str) and len(cover_val) > 100:
                            if not first_cover_b64:
                                first_cover_b64 = cover_val
                            meta['cover_b64_map'][fname] = cover_val

                for fname, info in files_node.items():
                    if isinstance(info, dict) and 'cover' in info:
                        cover_val = info['cover']
                        if cover_val == 'FIRST' and first_cover_b64:
                            meta['cover_b64_map'][fname] = first_cover_b64

        del data
    except Exception as e:
        print(f"[Scanner] YAML parsing error ({folder_path}): {e}")
        meta['parser_warnings'].append({
            'file_path': actual_yaml_path,
            'filename': os.path.basename(actual_yaml_path),
            'error_type': 'YamlParseError',
            'message': str(e)
        })

    meta['summary'] = clean_html_tags(meta['summary'])
    return meta