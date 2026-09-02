# -*- coding: utf-8 -*-
"""
custom_theme_service.py – 사용자 정의 테마(YAML) 로더/검증기

`themes/*.yaml` 디렉토리를 스캔해 각 파일을 화이트리스트 규격으로 검증하고,
통과한 테마만 `[data-app-theme="ID"] { --app-x: value; ... }` CSS로 변환한다.
플러그인처럼 "실행되는 코드"가 아니라 순수 데이터 파일이므로, 신뢰 경계는
"화이트리스트에 없는 키/정규식에 안 맞는 값은 파일 전체를 통째로 거부"로 처리한다
(부분 적용 금지 - 일부만 통과시키면 나머지 필드가 기본 테마 값으로 새어나가
의도치 않은 색 조합이 생길 수 있다).
"""
import os
import re
import threading

import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMES_DIR = os.path.join(BASE_DIR, 'themes')

# 기존 8개 내장 테마가 실제로 정의하는 CSS 변수 화이트리스트.
# app-shadow / app-blur 는 box-shadow/filter 문법이 열려있어 주입 표면이 넓으므로
# 스펙에서 아예 지원하지 않는다 (테마 가이드 문서에도 명시).
REQUIRED_VARS = (
    'app-bg-main', 'app-bg-sidebar', 'app-bg-card', 'app-bg-card-hover',
    'app-text-primary', 'app-text-muted', 'app-text-secondary',
    'app-accent', 'app-accent-hover', 'app-accent-contrast',
    'app-border', 'app-border-light', 'app-input-bg',
    'app-panel-rgb', 'app-panel-border-rgb',
)
REQUIRED_VARS_SET = set(REQUIRED_VARS)

# rgb 트리플릿(알파 없는 "R, G, B")으로 쓰이는 변수 - 나머지는 전부 hex 색상값
RGB_TRIPLET_VARS = {'app-panel-rgb', 'app-panel-border-rgb'}

BUILTIN_THEME_IDS = {'purple', 'dark', 'light', 'sepia', 'blue', 'aquamarine', 'ironman', 'epaper'}

ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')
HEX_RE = re.compile(r'^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?([0-9a-fA-F]{2})?$')
RGB_TRIPLET_RE = re.compile(r'^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$')

_lock = threading.Lock()
_cache = {
    'themes': [],       # [{'id':..., 'label':..., 'vars': {...}}, ...] (검증 통과분만)
    'rejected': [],      # [{'file':..., 'reason':...}, ...] (마지막 스캔 기준)
}


def _validate_rgb_triplet(value):
    m = RGB_TRIPLET_RE.match(str(value))
    if not m:
        return False
    return all(0 <= int(g) <= 255 for g in m.groups())


def _validate_theme_dict(data, filename):
    """(ok, error_reason_or_None, cleaned_theme_or_None)"""
    if not isinstance(data, dict):
        return False, 'YAML 최상위가 객체(map)가 아님', None

    theme_id = data.get('id')
    if not isinstance(theme_id, str) or not ID_RE.match(theme_id):
        return False, "'id'가 없거나 형식이 잘못됨 (영소문자/숫자/-/_, 32자 이내)", None
    if theme_id in BUILTIN_THEME_IDS:
        return False, f"'id'가 내장 테마와 충돌함: {theme_id}", None

    label = data.get('label')
    if not isinstance(label, str) or not (1 <= len(label.strip()) <= 60):
        return False, "'label'이 없거나 1~60자 문자열이 아님", None

    raw_vars = data.get('vars')
    if not isinstance(raw_vars, dict):
        return False, "'vars'가 없거나 객체(map)가 아님", None

    unknown_keys = set(raw_vars.keys()) - REQUIRED_VARS_SET
    if unknown_keys:
        return False, f"화이트리스트에 없는 키 포함: {', '.join(sorted(unknown_keys))}", None

    missing_keys = REQUIRED_VARS_SET - set(raw_vars.keys())
    if missing_keys:
        return False, f"필수 키 누락: {', '.join(sorted(missing_keys))}", None

    cleaned_vars = {}
    for key in REQUIRED_VARS:
        value = raw_vars[key]
        if not isinstance(value, str):
            return False, f"'{key}' 값이 문자열이 아님", None
        value = value.strip()
        if key in RGB_TRIPLET_VARS:
            if not _validate_rgb_triplet(value):
                return False, f"'{key}' 값이 'R, G, B'(0-255) 형식이 아님: {value}", None
        else:
            if not HEX_RE.match(value):
                return False, f"'{key}' 값이 hex 색상(#rgb/#rrggbb/#rrggbbaa)이 아님: {value}", None
        cleaned_vars[key] = value

    return True, None, {'id': theme_id, 'label': label.strip(), 'vars': cleaned_vars}


def load_themes():
    """themes/*.yaml, *.yml 을 스캔해 캐시를 갱신한다. (loaded_count, rejected_count) 반환."""
    themes = []
    rejected = []
    seen_ids = set()

    if os.path.isdir(THEMES_DIR):
        for entry in sorted(os.listdir(THEMES_DIR)):
            if not (entry.endswith('.yaml') or entry.endswith('.yml')):
                continue
            full_path = os.path.join(THEMES_DIR, entry)
            if not os.path.isfile(full_path):
                continue
            try:
                with open(full_path, 'r', encoding='utf-8') as fh:
                    data = yaml.safe_load(fh)
            except Exception as e:
                rejected.append({'file': entry, 'reason': f'YAML 파싱 실패: {e}'})
                continue

            ok, reason, cleaned = _validate_theme_dict(data, entry)
            if not ok:
                rejected.append({'file': entry, 'reason': reason})
                continue

            if cleaned['id'] in seen_ids:
                rejected.append({'file': entry, 'reason': f"id 중복 (이미 로드됨: {cleaned['id']})"})
                continue

            seen_ids.add(cleaned['id'])
            themes.append(cleaned)

    with _lock:
        _cache['themes'] = themes
        _cache['rejected'] = rejected

    return len(themes), len(rejected)


def get_themes():
    with _lock:
        return list(_cache['themes'])


def get_last_rejected():
    with _lock:
        return list(_cache['rejected'])


def generate_css():
    """검증 통과한 테마들을 `[data-app-theme="id"] { --app-x: value; }` CSS 텍스트로 변환."""
    parts = []
    for theme in get_themes():
        lines = [f'[data-app-theme="{theme["id"]}"] {{']
        for key, value in theme['vars'].items():
            lines.append(f'    --{key}: {value};')
        lines.append('}')
        parts.append('\n'.join(lines))
    return '\n\n'.join(parts)


# 서버 기동 시 최초 1회 스캔 (이후 재스캔은 관리자가 API로 트리거)
load_themes()
