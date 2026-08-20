# -*- coding: utf-8 -*-
import html
import os
import re
import textwrap
import threading
import time

import yaml

TARGET_FILENAME = 'kavita.yaml'

# 실제 HTML 태그만 매칭 (알파벳/슬래시/!로 시작) — 한국어 꺾쇠 표현 <책 제목> 보호
HTML_TAG_RE = re.compile(r'<[a-zA-Z/!][^>]*>')


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


def _normalize_misaligned_sequence_siblings(content):
    """`search:` 같은 시퀀스의 첫 항목만 `- Key: Value`로 대시가 붙고, 같은 항목에
    속해야 할 나머지 형제 키들(Month/Person Translator/...)이 대시 없이 대시와 같은
    들여쓰기로 나열되는, 특정 카테고리 kavita.yaml 생성 도구의 고질적인 오출력 패턴을
    보정한다.

        search:
            - Day: '22'      <- 정상 (시퀀스 항목 시작)
            Month: '03'      <- 잘못됨: Day와 같은 들여쓰기라 형제 키로 안 붙고
            Person Translator: ...   블록 파싱 자체가 깨짐(YAML 문법 오류)

    대시 다음 콘텐츠가 시작되는 컬럼까지 형제 키들을 재들여쓰기해서, 같은 매핑
    항목의 계속되는 줄로 인식되게 만든다. 대시 항목 직후 블록(들여쓰기가 대시와
    동일한 구간)에서만 좁게 동작하므로 정상 YAML을 건드릴 위험은 낮다.
    """
    lines = content.splitlines()
    out = list(lines)
    changed = False
    i = 0
    n = len(lines)
    while i < n:
        m = re.match(r'^([ \t]*)-([ \t]+)(\S.*:.*)$', lines[i])
        if not m:
            i += 1
            continue

        seq_indent = len(m.group(1))
        content_col = len(m.group(1)) + 1 + len(m.group(2))  # '-' + 뒤따르는 공백들 이후 컬럼

        j = i + 1
        while j < n:
            line = lines[j]
            if not line.strip():
                break
            sibling_indent = len(line) - len(line.lstrip(' \t'))
            if sibling_indent != seq_indent:
                break
            if line.lstrip(' \t').startswith('-'):
                break
            if not re.match(r'^\s*[^:]+:.*$', line):
                break
            out[j] = (' ' * content_col) + line.lstrip(' \t')
            changed = True
            j += 1

        i = j if j > i + 1 else i + 1

    return ('\n'.join(out), changed)


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

    # 1-b. 파싱 실패 시 들여쓰기(indent) 제거 후 재시도
    #      일부 kavita.yaml 생성 도구가 두 번째 줄부터 공통 들여쓰기를 넣는 경우 대응
    #      (예: 첫 줄 'Name: ...' 들여쓰기 없음, 이후 줄 '    Person: ...' 4칸 들여쓰기)
    if not parsed_ok:
        try:
            lines = raw_content.splitlines()
            # 두 번째 줄 이후의 비어있지 않은 줄에서 최소 들여쓰기 계산
            rest_lines = lines[1:] if len(lines) > 1 else []
            rest_non_empty = [ln for ln in rest_lines if ln.strip()]
            if rest_non_empty:
                min_indent = min(len(ln) - len(ln.lstrip()) for ln in rest_non_empty)
                if min_indent > 0:
                    # 첫 번째 줄은 그대로 유지, 두 번째 줄부터만 들여쓰기 제거
                    stripped_lines = [lines[0]] + [
                        ln[min_indent:] if ln.strip() else ln
                        for ln in rest_lines
                    ]
                    dedented = '\n'.join(stripped_lines)
                    data = yaml.load(dedented, Loader=SafeLoader) or {}
                    parsed_ok = True
        except Exception:
            pass

    # 1-c. 파싱 실패 시, 시퀀스 항목의 형제 키 들여쓰기 오류(특정 카테고리 생성 도구의
    #      고질적 패턴 - search: 블록 등)를 보정 후 재시도. 이게 성공하면 files:(커버
    #      Base64) 등 문서 나머지가 온전히 보존된 채로 파싱되므로 dash-normalize/정규식
    #      폴백보다 먼저 시도한다.
    if not parsed_ok:
        try:
            realigned_content, realigned = _normalize_misaligned_sequence_siblings(raw_content)
            if realigned:
                data = yaml.load(realigned_content, Loader=SafeLoader) or {}
                parsed_ok = True
                print(f"[Scanner] YAML 시퀀스 형제 키 들여쓰기 보정으로 파싱 복구 성공: {folder_path}")
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