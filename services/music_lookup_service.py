# -*- coding: utf-8 -*-
"""
music_lookup_service.py – 음악 앨범 외부 정보 조회 (album.yaml이 없을 때의 폴백)

- 대상: 오디오북 세션 '음악' 속성 카테고리의 앨범 중 아직 조회하지 않았고 album.yaml 정보가 없는 것
  (발매일·소개가 비어 있음). 차트 같은 모음집(앨범 아티스트 없음 + 곡 아티스트가 여러 명)은 앨범 단위
  조회가 의미 없어 'skipped'로 기록한다.
- 조회: 활성화된 메타데이터 플러그인 중 lookup_music_album(db_type, context)을 구현(오버라이드)한 것.
  먼저 결과를 준 플러그인을 쓴다. 외부 API 제한을 고려해 한 건마다 LOOKUP_INTERVAL_SEC 쉰다.
- 저장: audiobook_music_lookups (status found|not_found|skipped). 스캔이 덮어쓰지 않으며, 화면에는
  audiobooks의 빈 칸(아티스트/소개/커버)에만 겹쳐 보인다 - overlay_* 함수.
- 플러그인이 하나도 없으면 아무것도 기록하지 않는다(나중에 설치하면 그때부터 조회).
"""
import time

from plugins.metadata.base import BaseMetadataProvider

LOOKUP_INTERVAL_SEC = 5.0  # iTunes 등 무료 API의 분당 제한(약 20회)을 넘지 않게. 플러그인이 앨범당 1~3회 부를 수 있다
BATCH_SIZE = 20
CONTEXT_TRACK_TITLES = 5
HEALTH_KEY = ('music_lookup', '음악 앨범 정보 조회')


def _music_lookup_providers():
    """활성화됐고 lookup_music_album을 실제로 구현한 플러그인 인스턴스 목록."""
    from services.metadata_factory import MetadataFactory
    providers = []
    try:
        available = MetadataFactory.get_available_providers(include_view_ui=False, include_settings_ui=False)
    except Exception as e:
        print(f"[MusicLookup] provider discovery failed: {e}")
        return providers
    for meta in available:
        if not meta.get('enabled') or not meta.get('id'):
            continue
        try:
            provider = MetadataFactory.get_provider_by_id(meta['id'])
        except Exception:
            continue
        if type(provider).lookup_music_album is not BaseMetadataProvider.lookup_music_album:
            providers.append(provider)
    return providers


def is_compilation(album, tracks):
    artists = {str(t.get('artist') or '').strip() for t in tracks if str(t.get('artist') or '').strip()}
    return not str(album.get('author') or '').strip() and len(artists) > 1


def build_context(album, tracks):
    return {
        'folder_name': album.get('folder_name') or album.get('title') or '',
        'artist': str(album.get('author') or '').strip(),
        'track_titles': [t.get('title') or t.get('filename') or '' for t in tracks[:CONTEXT_TRACK_TITLES]],
        'track_count': len(tracks),
    }


def _clean_result(result, source):
    genres = result.get('genres')
    if isinstance(genres, (list, tuple)):
        genres = ', '.join(str(g).strip() for g in genres if str(g).strip())
    def text(key, limit):
        value = str(result.get(key) or '').strip()
        return value[:limit] or None
    return {
        'status': 'found', 'source': source,
        'artist': text('artist', 500), 'year': text('year', 20), 'genres': (str(genres).strip()[:500] or None) if genres else None,
        'summary': text('summary', 5000), 'cover_url': text('cover_url', 2000), 'source_url': text('source_url', 2000),
    }


def lookup_album(album, tracks, providers):
    """한 앨범 조회. 돌려주는 값: 저장할 dict, 또는 None(이번엔 기록하지 않음 - 플러그인 오류)."""
    if is_compilation(album, tracks):
        return {'status': 'skipped'}
    context = build_context(album, tracks)
    had_error = False
    for provider in providers:
        try:
            result = provider.lookup_music_album('audiobook', dict(context))
        except Exception as e:
            had_error = True
            print(f"[MusicLookup] provider={getattr(provider, 'id', '?')} album_id={album.get('id')} failed: {e}")
            continue
        if isinstance(result, dict) and any(result.get(k) for k in ('artist', 'year', 'summary', 'cover_url', 'genres')):
            return _clean_result(result, getattr(provider, 'id', None))
    return None if had_error else {'status': 'not_found'}


def run_pending(batch_size=BATCH_SIZE, interval_sec=LOOKUP_INTERVAL_SEC, sleep=time.sleep):
    """조회 대기 앨범을 최대 batch_size건 처리한다. 처리(기록)한 건수를 돌려준다."""
    from repositories.audiobook_repository import AudiobookRepository
    from services.system_health_service import SystemHealthService

    with SystemHealthService.track(*HEALTH_KEY):
        providers = _music_lookup_providers()
        if not providers:
            return 0
        done = 0
        for index, album in enumerate(AudiobookRepository.list_music_lookup_candidates(batch_size)):
            tracks = AudiobookRepository.get_audiobook_tracks(album['id'])
            values = lookup_album(album, tracks, providers)
            if values:
                AudiobookRepository.save_music_lookup(album['id'], values)
                done += 1
                print(f"[MusicLookup] album_id={album['id']} status={values['status']} source={values.get('source')}")
            if values is None or values.get('status') != 'skipped':
                sleep(interval_sec)  # 외부 API를 부른 경우만 쉰다
        return done


# ---- 화면에 겹쳐 보이기 (빈 칸만) ----

def get_found_lookup(audiobook_id):
    from repositories.audiobook_repository import AudiobookRepository
    try:
        row = AudiobookRepository.get_music_lookup(audiobook_id)
    except Exception as e:
        print(f"[MusicLookup] lookup read failed (audiobook_id={audiobook_id}): {e}")
        return None
    return row if row and row.get('status') == 'found' else None
