# -*- coding: utf-8 -*-
import importlib
import os
import sys
import html
import re
from threading import Lock

_loaded_parsers = None
_loader_lock = Lock()


def _metadata_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _base_meta():
    return {
        'title': '',
        'author': '',
        'publisher': '',
        'summary': '',
        'link': '',
        'score': 0,
        'release_date': '',
        'genre': '',
        'tags': '',
        'cover_b64_map': {},
        'cover_image_url': '',
        'is_webtoon': False,
        'has_yaml': False,
    }


HTML_TAG_RE = re.compile(r'<[^>]*>')


HANGUL_CONSONANTS = set(['ㄱ','ㄴ','ㄷ','ㄹ','ㅁ','ㅂ','ㅅ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ',
                         '가','나','다','라','마','바','사','아','자','차','카','타','파','하'])


def clean_html_tags(text):
    if not text:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p\s*>', '', text, flags=re.IGNORECASE)
    cleaned = HTML_TAG_RE.sub('', text)
    return html.unescape(cleaned).strip()


def normalize_metadata_token(token):
    """Normalize malformed genre/tag token (strip junk quote/bracket/comma marks)."""
    if token is None:
        return ''
    return re.sub(r'\s{2,}', ' ', str(token).strip(" \t\r\n'\"[](),")).strip()


def normalize_metadata_list_field(value):
    """Normalize comma-separated metadata list text and deduplicate while preserving order."""
    if not value:
        return ''

    tokens = [normalize_metadata_token(part) for part in str(value).split(',')]
    tokens = [t for t in tokens if t]

    normalized = []
    seen = set()
    for token in tokens:
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(token)

    return ', '.join(normalized)


def is_consonant_folder(foldername):
    foldername = foldername.strip()
    if foldername in HANGUL_CONSONANTS:
        return True
    if re.match(r'^[ㄱ-ㅎ]$', foldername):
        return True
    return False


def _merge_value(target, key, value):
    if key in ('genre', 'tags'):
        value = normalize_metadata_list_field(value)

    if key == 'cover_b64_map':
        if isinstance(value, dict) and value:
            target[key].update(value)
        return

    if key == 'score':
        if value not in (None, '', 0) and not target[key]:
            target[key] = value
        return

    if key == 'has_yaml':
        target[key] = bool(target[key] or value)
        return

    if key == 'is_webtoon':
        target[key] = bool(target[key] or value)
        return

    if value and not target.get(key):
        target[key] = value


def _has_target_file(folder_path, target_filename, files=None):
    if not target_filename:
        return False

    target_lower = target_filename.lower()
    if files is not None:
        return any(f.lower() == target_lower for f in files)

    try:
        if not os.path.exists(folder_path):
            return False
        for name in os.listdir(folder_path):
            if name.lower() == target_lower:
                return True
    except Exception:
        return False
    return False


def load_all_parsers():
    """Dynamically load scanner metadata parser modules once."""
    global _loaded_parsers
    if _loaded_parsers is not None:
        return _loaded_parsers

    with _loader_lock:
        if _loaded_parsers is not None:
            return _loaded_parsers

        loaded = []
        parser_dir = _metadata_dir()
        for file_name in sorted(os.listdir(parser_dir)):
            if not file_name.endswith('.py') or file_name.startswith('__'):
                continue

            module_name = file_name[:-3]
            module_path = f'{__name__}.{module_name}'
            try:
                module = importlib.import_module(module_path)
                target = getattr(module, 'TARGET_FILENAME', None)
                parser = getattr(module, 'parse', None)
                if target and callable(parser):
                    loaded.append(module)
            except Exception as e:
                print(f"[Scanner-Metadata] Failed to load parser '{module_name}': {e}", file=sys.stderr)

        _loaded_parsers = loaded
        return _loaded_parsers


def merge_local_metadata(folder_path, files=None, is_remote=False):
    """Merge local folder metadata using all loaded folder-level parser modules.

    Community contributors can add a self-contained module such as komga_yaml.py
    with TARGET_FILENAME = 'komga.yaml' and parse(...); it will be discovered and
    merged automatically as long as the target file exists in the folder.

    Archive-internal parsers such as ComicInfo.xml are intentionally excluded here
    because they are handled per-book in the archive scanning path.
    """
    parsers = load_all_parsers()

    merged = _base_meta()
    for parser_module in parsers:
        target_filename = getattr(parser_module, 'TARGET_FILENAME', None)
        parser_fn = getattr(parser_module, 'parse', None)
        if not callable(parser_fn):
            continue

        if target_filename and target_filename.lower() == 'comicinfo.xml':
            continue

        if not _has_target_file(folder_path, target_filename, files=files):
            continue

        try:
            source = parser_fn(folder_path, files=files, is_remote=is_remote)
        except TypeError:
            try:
                source = parser_fn(folder_path, is_remote=is_remote)
            except TypeError:
                source = parser_fn(folder_path)
        except Exception as e:
            print(f"[Scanner-Metadata] Parser '{getattr(parser_module, '__name__', 'unknown')}' failed: {e}", file=sys.stderr)
            continue

        if not isinstance(source, dict):
            continue

        for key, value in source.items():
            _merge_value(merged, key, value)

    merged['genre'] = normalize_metadata_list_field(merged.get('genre', ''))
    merged['tags'] = normalize_metadata_list_field(merged.get('tags', ''))

    return merged


from .info_xml import parse_info_xml
from .kavita_yaml import parse_kavita_yaml
from .series_json import parse_series_json
from .comicinfo_xml import parse_comicinfo_from_cbz
from .audio_json import parse_audio_json