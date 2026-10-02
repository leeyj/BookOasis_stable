# -*- coding: utf-8 -*-
"""
music_enrich_service.py – 원격 음악 곡 정보를 "재생할 때" 채운다

원격 마운트(GDS 등)의 음악 카테고리 스캔은 곡 파일을 열지 않는다(audiobook_scanner.parse_audiobook_folder
참고 - rclone VFS는 태그만 읽어도 파일 전체를 내려받는다). 그래서 길이가 0이고 제목은 album.yaml/파일명이다.
곡이 재생되면 그 파일은 이미 rclone 캐시에 들어오므로, 그때 태그·길이·내장 아트를 읽어 채우면 공유
드라이브에 추가 요청이 없다.

- stream 요청에서 길이가 0인 곡이면 ENRICH_DELAY_SEC 뒤 백그라운드로 한 번 읽는다(앞부분이 캐시된 뒤).
- 같은 곡을 동시에 여러 번 예약하지 않는다(Range 요청이 곡마다 여러 번 온다).
- 채우는 것: 곡 길이, 태그 제목/아티스트(태그가 있을 때만 덮음), 앨범 총 재생시간,
  비어 있으면 앨범 아티스트(곡 아티스트 다수결)와 포스터(이 곡의 내장 아트).
"""
import os
import threading
from collections import Counter

ENRICH_DELAY_SEC = 15.0

_lock = threading.Lock()
_scheduled = set()


def needs_enrich(track_row):
    return bool(track_row) and float(track_row.get('duration') or 0.0) <= 0.0


def probe_track(file_path):
    """(길이, (제목, 아티스트)) - 이미 캐시된 곡 파일에서 읽는다."""
    from services.audiobook_scanner import (
        _probe_music_duration_and_tags,
        estimate_mp3_duration,
        read_music_tags,
    )
    if file_path.lower().endswith('.mp3'):
        try:
            size = os.path.getsize(file_path)
        except OSError:
            size = 0
        return estimate_mp3_duration(file_path, size, remote_fast_path=True), read_music_tags(file_path)
    duration, tags = _probe_music_duration_and_tags(file_path)
    return duration, (tags or (None, None))


def enrich_track(audiobook_id, track_id):
    """한 곡을 채운다. 채웠으면 True."""
    from repositories.audiobook_repository import AudiobookRepository
    from services.audiobook_scanner import read_embedded_cover

    track = AudiobookRepository.get_track_by_id_and_audiobook_id(track_id, audiobook_id)
    if not needs_enrich(track) or not track.get('file_path'):
        return False
    path = track['file_path']
    duration, (title, artist) = probe_track(path)
    if duration <= 0:
        return False
    AudiobookRepository.update_track_probe(track_id, duration, title, artist)

    album = AudiobookRepository.get_audiobook_by_id(audiobook_id) or {}
    author = None
    if not str(album.get('author') or '').strip():
        tracks = AudiobookRepository.get_audiobook_tracks(audiobook_id)
        top = Counter(str(t.get('artist') or '').strip() for t in tracks if str(t.get('artist') or '').strip()).most_common(1)
        if top and top[0][1] * 2 >= len(tracks):
            author = top[0][0]
    poster = None
    if not str(album.get('poster') or '').strip() and read_embedded_cover(path):
        poster = os.path.normpath(path)
    AudiobookRepository.refresh_enriched_album(audiobook_id, author=author, poster=poster)
    print(f"[MusicEnrich] audiobook_id={audiobook_id} track_id={track_id} duration={duration:.1f} "
          f"tags={'yes' if title else 'no'} author_set={bool(author)} poster_set={bool(poster)}")
    return True


def _run(audiobook_id, track_id):
    try:
        enrich_track(audiobook_id, track_id)
    except Exception as e:
        print(f"[MusicEnrich] audiobook_id={audiobook_id} track_id={track_id} failed: {e}")
    finally:
        with _lock:
            _scheduled.discard((audiobook_id, track_id))


def schedule_track_enrich(audiobook_id, track_row, delay_sec=None):
    """stream 요청에서 부른다. 채울 필요가 없거나 이미 예약됐으면 아무것도 하지 않는다."""
    if not needs_enrich(track_row):
        return False
    key = (int(audiobook_id), int(track_row['id']))
    with _lock:
        if key in _scheduled:
            return False
        _scheduled.add(key)
    timer = threading.Timer(ENRICH_DELAY_SEC if delay_sec is None else delay_sec, _run, args=key)
    timer.daemon = True
    timer.start()
    return True
