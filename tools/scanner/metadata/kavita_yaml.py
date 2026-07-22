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


KNOWN_KAVITA_KEYS = {
    'title', 'series', 'author', 'publisher', 'summary', 'description', 'isbn',
    'score', 'link', 'genre', 'genres', 'tags', 'tag', 'cover_b64_map', 'meta',
    'search', 'person publisher', 'person writers', 'web links', 'writer'
}


def _normalize_dash_prefixed_mapping_lines(content):
    """Convert top-level dash-prefixed mapping lines into plain mapping lines for loose YAML fallbacks."""
    normalized_lines = []
    changed = False

    for line in content.splitlines():
        match = re.match(r'^(\s*)-\s*([^:]+?)\s*:\s*(.*)$', line)
        if match:
            indent, key, value = match.groups()
            key_clean = key.strip().lower()
            # 들여쓰기가 거의 없거나(0~2칸) 알려진 루트 키인 경우에만 - Key: Value 대시 제거
            if len(indent) <= 2 or key_clean in KNOWN_KAVITA_KEYS:
                normalized_lines.append(f"{indent}{key.strip()}: {value}")
                changed = True
                continue

        normalized_lines.append(line)

    return ('\n'.join(normalized_lines), changed)


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
    parse_started_at = time.monotonic()

    try:
        from yaml import CSafeLoader as SafeLoader
    except ImportError:
        from yaml import SafeLoader

    raw_content = read_file_with_timeout(actual_yaml_path, is_remote)
    if raw_content is None:
        return meta

    data = {}
    parsed_ok = False

    # 1. 표준 YAML 로딩을 먼저 원본 내용으로 시도 (정상적인 - 리스트 문법 보호)
    try:
        data = yaml.load(raw_content, Loader=SafeLoader) or {}
        parsed_ok = True
    except Exception:
        pass

    # 2. 원본 파싱 실패 시, 오탈자(- Key: Value) 보정 후 2차 시도
    normalized_dash_lines = False
    if not parsed_ok:
        content, normalized_dash_lines = _normalize_dash_prefixed_mapping_lines(raw_content)
        try:
            data = yaml.load(content, Loader=SafeLoader) or {}
            parsed_ok = True
        except Exception as e:
            if normalized_dash_lines:
                print(f"[Scanner] YAML parsing error ({folder_path}): {e}. Dash-prefixed mapping lines were normalized; running Regex Fallback Parser...")
            else:
                print(f"[Scanner] YAML parsing error ({folder_path}): {e}. Running Regex Fallback Parser...")
            meta['parser_warnings'].append({
                'file_path': actual_yaml_path,
                'filename': os.path.basename(actual_yaml_path),
                'error_type': 'YamlParseError',
                'message': f"YAML Parse failed, fallback active: {e}"
            })
            # 3. Regex Fallback Parser 기동
            try:
                fallback_started_at = time.monotonic()
                for line in content.splitlines():
                    match = re.match(r'^\s*-?\s*([^:]{2,80}?)\s*:\s*(.*)$', line)
                    if match:
                        key = match.group(1).strip()
                        val = match.group(2).strip()
                        if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
                            val = val[1:-1]
                        data[key] = val
                fallback_elapsed_ms = (time.monotonic() - fallback_started_at) * 1000.0
                print(f"[Scanner] YAML Regex Fallback completed ({folder_path}) in {fallback_elapsed_ms:.1f}ms")
            except Exception as fallback_err:
                print(f"[Scanner] YAML Regex Fallback also failed ({folder_path}): {fallback_err}")

    try:
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
        print(f"[Scanner] YAML data processing error ({folder_path}): {e}")
        meta['parser_warnings'].append({
            'file_path': actual_yaml_path,
            'filename': os.path.basename(actual_yaml_path),
            'error_type': 'YamlParseError',
            'message': str(e)
        })

    meta['summary'] = clean_html_tags(meta['summary'])
    parse_elapsed_ms = (time.monotonic() - parse_started_at) * 1000.0
    print(f"[Scanner] YAML metadata parse finished ({folder_path}) in {parse_elapsed_ms:.1f}ms")
    return meta