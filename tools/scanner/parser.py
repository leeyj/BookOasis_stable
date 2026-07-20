# -*- coding: utf-8 -*-
"""Legacy scanner parser compatibility module.

New scanner parser modules must be self-contained under tools/scanner/metadata/
and must not import this module for shared helpers.
"""
import os
import re
import html
import yaml
import time
import threading
import xml.etree.ElementTree as ET

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
            if self.failures == self.max_failures:
                print(f"[Scanner-CircuitBreaker] 🚨 VFS read timeouts exceeded {self.max_failures} times. Circuit tripped! Skipping all VFS reads for {self.reset_timeout}s.")
            
    def record_success(self):
        with self._lock:
            if self.failures > 0:
                self.failures = 0

_circuit_breaker = NetworkCircuitBreaker(max_failures=3, reset_timeout=60)

HTML_TAG_RE = re.compile(r'<[^>]*>')

# Korean initial consonant list and consonant branch folder discriminant regex (e.g., ㄱ, ㄴ, 아, 자, 타)
HANGUL_CONSONANTS = set(['ㄱ','ㄴ','ㄷ','ㄹ','ㅁ','ㅂ','ㅅ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ',
                         '가','나','다','라','마','바','사','아','자','차','카','타','파','하'])

def clean_html_tags(text):
    """Remove HTML tags and restore special entities"""
    if not text:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p\s*>', '', text, flags=re.IGNORECASE)
    cleaned = HTML_TAG_RE.sub('', text)
    return html.unescape(cleaned).strip()

def read_file_with_timeout(file_path, is_remote, timeout=10):
    """
    Reads a file with a strict timeout using a daemon thread if is_remote is True.
    Returns the file content as a string, or None if it times out or errors.
    """
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
        print(f"[Scanner-Timeout] ⚠️ VFS file read timed out ({timeout}s): {file_path}")
        _circuit_breaker.record_failure()
        return None
        
    if not result:
        _circuit_breaker.record_failure()
        return None
        
    res = result[0]
    if isinstance(res, Exception):
        # File not found or permission error, not a timeout/network hang. Don't trip breaker for normal IO errors.
        return None
        
    _circuit_breaker.record_success()
    return res

def is_consonant_folder(foldername):
    """Determine if folder name is initial consonant/index folder (Korean, English, numeric, etc.)"""
    foldername = foldername.strip()
    # 한글 초성 / 음절 색인 폴더 (ㄱ, ㄴ... / 가, 나...)
    if foldername in HANGUL_CONSONANTS:
        return True
    if re.match(r'^[ㄱ-ㅎ]$', foldername):
        return True
    # 영문 단일 알파벳 색인 폴더 (A, B, ... Z)
    if re.match(r'^[A-Za-z]$', foldername):
        return True
    # 숫자 또는 영숫자 혼합 단독 색인 폴더 (0, 1, 0-9, 0Z, A1 등, 최대 3자)
    if re.match(r'^[A-Za-z0-9]{1,3}$', foldername):
        return True
    # 흔한 기타/특수문자 색인 폴더명
    if foldername.lower() in {'기타', 'etc', 'other', 'others', 'misc', '#', '!', '_', '-', '0-9', 'a-z', 'z'}:
        return True
    return False

def parse_info_xml(folder_path, files=None, is_remote=False):
    """Read info.xml in folder and parse metadata"""
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

def parse_kavita_yaml(folder_path, files=None, is_remote=False):
    """Read kavita.yaml in folder and parse metadata"""
    yaml_path = os.path.join(folder_path, 'kavita.yaml')
    meta = {
        'author': '',
        'publisher': '',
        'summary': '',
        'score': 0,
        'link': '',
        'genre': '',
        'tags': '',
        'cover_b64_map': {},
        'has_yaml': False
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
        # Search ignoring case by directly scanning directory if no file list
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
        
    content = read_file_with_timeout(actual_yaml_path, is_remote)
    if content is None:
        return meta
        
    # 1차 보정: 비정상적인 "- Key: Value" 문법을 "Key: Value"로 보정 (공백 유무 자비 허용)
    import re
    content = re.sub(r'^\s*-\s*([a-zA-Z0-9_\s]+)\s*:', r'\1:', content, flags=re.MULTILINE)

    data = {}
    try:
        data = yaml.load(content, Loader=SafeLoader) or {}
    except Exception as e:
        print(f"[Scanner] YAML parsing error ({folder_path}): {e}. Running Regex Fallback Parser...")
        # 2차 보정: Regex Fallback Parser 기동
        try:
            for line in content.splitlines():
                match = re.match(r'^\s*-?\s*([a-zA-Z0-9_\s]{2,40})\s*:\s*(.*)$', line)
                if match:
                    key = match.group(1).strip()
                    val = match.group(2).strip()
                    if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
                        val = val[1:-1]
                    data[key] = val
        except Exception as fallback_err:
            print(f"[Scanner] YAML Regex Fallback also failed ({folder_path}): {fallback_err}")

    try:
        def _parse_list_or_str(val):
            if not val:
                return ''
            if isinstance(val, list):
                return ', '.join(str(v).strip() for v in val if v)
            return str(val).strip()

        # 1) Include root level (data) in search scope in case meta node is not explicitly specified
        if isinstance(data, dict):
            sources = [data.get('meta', {}), data]
            for src in sources:
                if not isinstance(src, dict): continue
                meta['publisher'] = meta['publisher'] or src.get('Person Publisher') or src.get('publisher') or ''
                meta['author'] = meta['author'] or src.get('Person Writers') or src.get('Writer') or src.get('author') or ''
                meta['summary'] = meta['summary'] or src.get('Summary') or src.get('summary') or ''
                meta['link'] = meta['link'] or src.get('Web Links') or src.get('link') or ''
                meta['tags'] = meta['tags'] or _parse_list_or_str(src.get('Tags') or src.get('tags') or src.get('tag'))
                meta['genre'] = meta['genre'] or _parse_list_or_str(src.get('Genres') or src.get('genre'))
                
            # 2) Reinforce if search node exists
            search_list = data.get('search', [])
            if search_list and isinstance(search_list, list) and len(search_list) > 0:
                search_item = search_list[0]
                if isinstance(search_item, dict):
                    meta['author'] = meta['author'] or search_item.get('author', '')
                    meta['publisher'] = meta['publisher'] or search_item.get('publisher', '')
                    meta['link'] = meta['link'] or search_item.get('link', '')
                    meta['summary'] = meta['summary'] or search_item.get('description', '')
                    meta['score'] = search_item.get('score', meta['score'])
                    meta['tags'] = meta['tags'] or _parse_list_or_str(search_item.get('tag') or search_item.get('tags') or search_item.get('Tags'))
                    meta['genre'] = meta['genre'] or _parse_list_or_str(search_item.get('genre') or search_item.get('genres') or search_item.get('Genres'))
                
            # Cover image for each file
            files_node = data.get('files', {})
            first_cover_b64 = None
            if isinstance(files_node, dict):
                # 1. First find and save first cover with actual Base64 data
                for fname, info in files_node.items():
                    if isinstance(info, dict) and 'cover' in info:
                        cover_val = info['cover']
                        if cover_val and isinstance(cover_val, str) and len(cover_val) > 100:
                            if not first_cover_b64:
                                first_cover_b64 = cover_val
                            meta['cover_b64_map'][fname] = cover_val
                            
                # 2. Iterate again and apply copy to first cover if 'FIRST' directive exists
                for fname, info in files_node.items():
                    if isinstance(info, dict) and 'cover' in info:
                        cover_val = info['cover']
                        if cover_val == 'FIRST' and first_cover_b64:
                            meta['cover_b64_map'][fname] = first_cover_b64
        
        # Explicitly clear temporary parsing dictionary to help garbage collection
        del data
    except Exception as e:
        print(f"[Scanner] YAML parsing error ({folder_path}): {e}")
        
    meta['summary'] = clean_html_tags(meta['summary'])
    return meta

def parse_series_json(folder_path, files=None, is_remote=False):
    """Read series.json in folder and parse metadata (for webtoon)"""
    import json
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

def parse_comicinfo_from_cbz(file_path):
    """Parse ComicInfo.xml inside CBZ/ZIP file and return metadata.
    Fully compatible with Kavita standard format.
    Returns empty metadata on remote path or file access failure.
    """
    import zipfile
    import io

    meta = {
        'author': '',
        'publisher': '',
        'summary': '',
        'release_date': '',
        'genre': '',
        'tags': '',
        'cover_b64': None,     # Cover image data in ComicInfo.xml (if exists)
    }

    if not file_path.lower().endswith(('.cbz', '.zip')):
        return meta

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Search ComicInfo.xml ignoring case
            names_lower = {n.lower(): n for n in zf.namelist()}
            comicinfo_key = names_lower.get('comicinfo.xml')
            if not comicinfo_key:
                return meta

            xml_data = zf.read(comicinfo_key)
            root = ET.fromstring(xml_data)

            def _get(tag):
                elem = root.find(tag)
                return elem.text.strip() if elem is not None and elem.text else ''

            # Author: Search in order of Writer -> Penciller -> Artist
            author = _get('Writer') or _get('Penciller') or _get('Artist')
            meta['author'] = author
            meta['publisher'] = _get('Publisher')
            meta['summary'] = clean_html_tags(_get('Summary'))
            meta['genre'] = _get('Genre')
            meta['tags'] = _get('Tags')

            # Combine publish date
            year = _get('Year')
            month = _get('Month').zfill(2) if _get('Month') else ''
            day = _get('Day').zfill(2) if _get('Day') else ''
            if year:
                meta['release_date'] = f"{year}-{month or '01'}-{day or '01'}"

    except zipfile.BadZipFile:
        pass  # Silently skip corrupted files
    except Exception as e:
        print(f"[Scanner] ComicInfo.xml parsing error ({file_path}): {e}")

    return meta
