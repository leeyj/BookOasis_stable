# -*- coding: utf-8 -*-
"""
music_lyrics_service.py – 음악 카테고리 곡 가사 (재생 시점에 읽는다, DB에 저장하지 않음)

찾는 순서:
  1. 앨범 폴더의 album.yaml  tracks[디스크][트랙].lyrics  (LRC 싱크 가사가 대부분)
  2. 곡 파일 태그  - FLAC/Ogg 'lyrics'·'unsyncedlyrics', MP3 USLT 프레임, M4A '©lyr'
     (여러 개면 시간 태그가 있는 것을 우선)

돌려주는 값: {'source': 'album_yaml'|'tag'|None, 'synced': bool, 'lines': [{'t': 초|None, 'text': str}]}
album.yaml은 폴더 경로+수정 시각 기준으로 프로세스 메모리에 캐시한다(원격 마운트 재조회 최소화).
"""
import os
import re

ALBUM_YAML_NAME = 'album.yaml'

_LRC_TIME_RE = re.compile(r'\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]')
_LRC_META_RE = re.compile(r'^\[(ar|ti|al|by|offset|length|re|ve|au):', re.IGNORECASE)
_TITLE_NORM_RE = re.compile(r'[\s\W_]+', re.UNICODE)

_album_yaml_cache = {}


def _norm_title(title):
    return _TITLE_NORM_RE.sub('', str(title or '')).lower()


def load_album_yaml(folder_path):
    """앨범 폴더의 album.yaml을 dict로 읽는다(없거나 깨졌으면 None). 수정 시각 기준 캐시."""
    path = os.path.join(folder_path, ALBUM_YAML_NAME)
    try:
        mtime = os.stat(path).st_mtime_ns
    except OSError:
        return None
    cached = _album_yaml_cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    data = None
    try:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            loaded = yaml.safe_load(f)
        data = loaded if isinstance(loaded, dict) else None
    except Exception as e:
        print(f"[MusicLyrics] album.yaml read failed ({path}): {e}")
    _album_yaml_cache[path] = (mtime, data)
    return data


def album_yaml_tracks(album_yaml):
    """tracks[디스크][트랙] → (디스크, 트랙) 순서의 평평한 목록 [{'title', 'lyrics', ...}]."""
    tracks = (album_yaml or {}).get('tracks')
    if not isinstance(tracks, dict):
        return []

    def num(value):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 0

    flat = []
    for disc in sorted(tracks, key=num):
        entries = tracks[disc]
        if not isinstance(entries, dict):
            continue
        for no in sorted(entries, key=num):
            entry = entries[no]
            if isinstance(entry, dict):
                flat.append(entry)
    return flat


def match_album_yaml_entry(entries, track_title, track_index, track_count):
    """곡 → album.yaml 항목. 제목(공백/기호 무시)이 같은 항목을 먼저, 없으면 곡 수가 같을 때 순서로."""
    key = _norm_title(track_title)
    if key:
        for entry in entries:
            if _norm_title(entry.get('title')) == key:
                return entry
    if entries and len(entries) == track_count and 0 <= track_index < track_count:
        return entries[track_index]
    return None


def parse_lyrics(text):
    """LRC 또는 일반 텍스트 → [{'t': 초|None, 'text'}]. 한 줄에 시간 태그가 여러 개면 각 시각으로 펼친다."""
    lines = []
    synced = False
    for raw in str(text or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        stripped = raw.strip()
        if _LRC_META_RE.match(stripped):
            continue
        times = list(_LRC_TIME_RE.finditer(stripped))
        if times and times[0].start() == 0:
            body = _LRC_TIME_RE.sub('', stripped).strip()
            for m in times:
                minutes, seconds, frac = int(m.group(1)), int(m.group(2)), m.group(3) or '0'
                lines.append({'t': round(minutes * 60 + seconds + int(frac) / (10 ** len(frac)), 3), 'text': body})
            synced = True
        else:
            lines.append({'t': None, 'text': stripped})
    if synced:
        # 시간 없는 줄(머리말 등)은 버리고 시각 순으로
        lines = sorted((l for l in lines if l['t'] is not None), key=lambda l: l['t'])
    else:
        # 앞뒤 빈 줄 정리
        while lines and not lines[0]['text']:
            lines.pop(0)
        while lines and not lines[-1]['text']:
            lines.pop()
    return synced, lines


def _pick_text(candidates):
    """후보 가사 중 시간 태그가 있는 것을 우선, 그다음 긴 것."""
    texts = [str(c).strip() for c in candidates if c and str(c).strip()]
    if not texts:
        return None
    return sorted(texts, key=lambda t: (bool(_LRC_TIME_RE.search(t)), len(t)), reverse=True)[0]


def _album_yaml_lyrics(entry):
    if not entry:
        return None
    raw = entry.get('lyrics')
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        lrc = [item.get('data') for item in raw if isinstance(item, dict) and str(item.get('format', '')).lower() == 'lrc']
        other = [item.get('data') if isinstance(item, dict) else item for item in raw]
        return _pick_text(lrc) or _pick_text(other)
    return None


def read_tag_lyrics(file_path):
    """곡 파일 태그의 가사. 태그 영역만 읽는다."""
    try:
        if file_path.lower().endswith('.mp3'):
            from mutagen.id3 import ID3
            tags = ID3(file_path)
            return _pick_text([frame.text for frame in tags.getall('USLT')])
        import mutagen
        audio = mutagen.File(file_path)
        tags = audio.tags if audio is not None else None
        if not tags:
            return None
        candidates = []
        if hasattr(tags, 'getall'):  # ID3 계열 컨테이너
            candidates += [frame.text for frame in tags.getall('USLT')]
        for key in ('lyrics', 'LYRICS', 'unsyncedlyrics', 'UNSYNCEDLYRICS', '\xa9lyr'):
            try:
                value = tags.get(key)
            except Exception:
                value = None
            if isinstance(value, (list, tuple)):
                candidates += [str(v) for v in value]
            elif value:
                candidates.append(str(value))
        return _pick_text(candidates)
    except Exception:
        return None


def get_track_lyrics(folder_path, file_path, track_title, track_index, track_count):
    text, source = None, None
    if folder_path:
        entry = match_album_yaml_entry(album_yaml_tracks(load_album_yaml(folder_path)), track_title, track_index, track_count)
        text = _album_yaml_lyrics(entry)
        source = 'album_yaml' if text else None
    if not text and file_path:
        text = read_tag_lyrics(file_path)
        source = 'tag' if text else None
    if not text:
        return {'source': None, 'synced': False, 'lines': []}
    synced, lines = parse_lyrics(text)
    return {'source': source, 'synced': synced, 'lines': lines}
