"""음악 앨범 외부 정보 조회 (lookup_music_album 플러그인 폴백): 코어 서비스 + 저장소 + iTunes 샘플 플러그인.

외부 API는 부르지 않는다(플러그인 검색 함수를 바꿔 끼운다).
"""
import sqlite3
from contextlib import contextmanager

import pytest

from plugin_framework.metadata_base import BaseMetadataProvider
from repositories.sqlite import audiobook_repository as sqlite_repo
from sample_plugins.metadata.music_itunes.music_itunes import (
    MusicItunesMetadataProvider,
    clean_album_title,
    pick_best,
)
from services import music_lookup_service as lookup
from services.db_migration_service import _SCHEMA_SQL


# ---- iTunes 샘플 플러그인 ----

@pytest.mark.parametrize('folder, expected', [
    ('[2008.01.17 정규앨범] Andy The First New Dream', 'Andy The First New Dream'),
    ('[2007.11.30 싱글EP] 엉뚱한 상상 (Digital Single)', '엉뚱한 상상'),
    ('Palette', 'Palette'),
    ('[2019] [정규] Momentary Sixth Sense [MQA]', 'Momentary Sixth Sense'),
    ('Olivia Ong - Romance (2011)', 'Olivia Ong - Romance'),
    ('Yao Si Ting - Yao Si Ting Collection (JVC, 2010) [XRCD]', 'Yao Si Ting - Yao Si Ting Collection'),
    ('Love Song (Feat. 채연)', 'Love Song (Feat. 채연)'),
])
def test_folder_prefix_and_noise_are_removed_before_searching(folder, expected):
    assert clean_album_title(folder) == expected


def _album(artist, name, year='2017-04-21T07:00:00Z'):
    return {'artistName': artist, 'collectionName': name, 'releaseDate': year, 'primaryGenreName': 'K-Pop',
            'artworkUrl100': 'https://x/100x100bb.jpg', 'collectionViewUrl': f'https://music/{name}'}


def test_same_title_by_another_artist_is_rejected():
    results = [_album('KIMMUSEUM', 'Palette - Single'), _album('eill', 'PALETTE')]
    assert pick_best(results, 'Palette', ['윤하']) is None
    assert pick_best(results, 'Palette', ['eill'])['artistName'] == 'eill'


def test_korean_artist_name_is_matched_through_store_aliases(monkeypatch):
    plugin = MusicItunesMetadataProvider()
    plugin._alias_cache = {}
    plugin.get_plugin_config = lambda *a, **k: {}
    calls = []

    def fake_search(term, entity, limit):
        calls.append((term, entity))
        if entity == 'musicArtist':
            return [{'artistName': 'SHINHWA'}, {'artistName': 'ANDY'}]
        return [_album('ANDY', 'Andy the First New Dream', '2008-01-17T08:00:00Z')]

    monkeypatch.setattr(plugin, '_search', fake_search)
    result = plugin.lookup_music_album('audiobook', {'folder_name': '[2008.01.17 정규앨범] Andy The First New Dream',
                                                     'artist': '앤디'})
    assert result == {'artist': 'ANDY', 'year': '2008', 'genres': ['K-Pop'], 'cover_url': 'https://x/600x600bb.jpg',
                      'source_url': 'https://music/Andy the First New Dream'}
    # 같은 가수의 다음 앨범은 별칭을 다시 묻지 않는다
    plugin.lookup_music_album('audiobook', {'folder_name': 'Single Man', 'artist': '앤디'})
    assert sum(1 for _, entity in calls if entity == 'musicArtist') == 1


# ---- 코어 조회 서비스 ----

class FakeProvider(BaseMetadataProvider):
    id = 'fake_music'

    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.contexts = answer, error, []

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, ''

    def lookup_music_album(self, db_type, context):
        self.contexts.append(context)
        if self.error:
            raise self.error
        return self.answer


class NotImplementing(BaseMetadataProvider):
    id = 'other'

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, ''


ALBUM = {'id': 1, 'folder_name': '[2017.04.21 정규앨범] Palette', 'title': '[2017.04.21 정규앨범] Palette', 'author': '아이유'}
TRACKS = [{'title': 'Palette', 'artist': '아이유'}, {'title': '이런 엔딩', 'artist': '아이유'}]


def test_found_result_is_cleaned_and_records_the_source():
    provider = FakeProvider({'artist': 'IU', 'year': '2017', 'genres': ['K-Pop', 'Pop'], 'cover_url': 'https://c'})
    values = lookup.lookup_album(ALBUM, TRACKS, [provider])
    assert values['status'] == 'found' and values['source'] == 'fake_music'
    assert (values['artist'], values['year'], values['genres'], values['cover_url']) == ('IU', '2017', 'K-Pop, Pop', 'https://c')
    assert provider.contexts == [{'folder_name': '[2017.04.21 정규앨범] Palette', 'artist': '아이유',
                                  'track_titles': ['Palette', '이런 엔딩'], 'track_count': 2}]


def test_compilations_are_skipped_without_asking_plugins():
    provider = FakeProvider({'artist': 'x'})
    chart = {'id': 2, 'folder_name': '[멜론] 2024.08 월간 TOP 100 FLAC', 'author': ''}
    tracks = [{'title': 'Supernova', 'artist': 'aespa'}, {'title': 'Klaxon', 'artist': '(여자)아이들'}]
    assert lookup.lookup_album(chart, tracks, [provider]) == {'status': 'skipped'}
    assert provider.contexts == []


def test_not_found_is_remembered_but_a_plugin_error_is_retried_later():
    assert lookup.lookup_album(ALBUM, TRACKS, [FakeProvider(None)]) == {'status': 'not_found'}
    assert lookup.lookup_album(ALBUM, TRACKS, [FakeProvider(error=RuntimeError('429'))]) is None
    # 앞 플러그인이 실패해도 다음 플러그인이 찾으면 그 결과
    found = lookup.lookup_album(ALBUM, TRACKS, [FakeProvider(error=RuntimeError('x')), FakeProvider({'year': '2017'})])
    assert found['status'] == 'found' and found['year'] == '2017'


def test_only_plugins_that_override_the_contract_are_used(monkeypatch):
    from services.metadata_factory import MetadataFactory
    instances = {'fake_music': FakeProvider(), 'other': NotImplementing(), 'off': FakeProvider()}
    monkeypatch.setattr(MetadataFactory, 'get_available_providers', classmethod(lambda cls, **k: [
        {'id': 'fake_music', 'enabled': True}, {'id': 'other', 'enabled': True}, {'id': 'off', 'enabled': False}]))
    monkeypatch.setattr(MetadataFactory, 'get_provider_by_id', classmethod(lambda cls, pid: instances[pid]))
    assert lookup._music_lookup_providers() == [instances['fake_music']]


# ---- 저장소 (SQLite) + run_pending ----

class _NonClosing:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


@pytest.fixture
def audiobook_db(monkeypatch):
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    connection.execute("INSERT INTO libraries (id, name, physical_path, content_kind) VALUES (1, 'music', '/m', 'music')")
    connection.execute("INSERT INTO libraries (id, name, physical_path, content_kind) VALUES (2, 'books', '/b', 'unspecified')")
    rows = [
        (10, 1, 'Palette', '/m/Palette', '아이유', '', ''),          # 대상
        (11, 1, 'Andy', '/m/Andy', '앤디', '2008-01-17', ''),        # album.yaml 있음(발매일) → 제외
        (12, 2, 'Book', '/b/Book', '저자', '', ''),                  # 음악 카테고리 아님 → 제외
    ]
    for aid, lib, title, path, author, premiered, desc in rows:
        connection.execute(
            "INSERT INTO audiobooks (id, library_id, title, folder_name, folder_path, author, premiered, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (aid, lib, title, title, path, author, premiered, desc))
    connection.execute("INSERT INTO audiobook_tracks (audiobook_id, track_number, filename, file_path, title, artist) "
                       "VALUES (10, 1, '01', '/m/Palette/01.flac', 'Palette', '아이유')")
    wrapper = _NonClosing(connection)

    @contextmanager
    def fake_connection(_db_type):
        yield wrapper

    monkeypatch.setattr(sqlite_repo.database, 'connection', fake_connection)
    monkeypatch.setattr('repositories.audiobook_repository.AudiobookRepository', sqlite_repo.AudiobookRepository)
    return connection


def test_candidates_are_music_albums_without_album_yaml_info_not_looked_up_yet(audiobook_db):
    repo = sqlite_repo.AudiobookRepository
    assert [r['id'] for r in repo.list_music_lookup_candidates(10)] == [10]
    repo.save_music_lookup(10, {'status': 'not_found'})
    assert repo.list_music_lookup_candidates(10) == []
    repo.save_music_lookup(10, {'status': 'found', 'artist': 'IU', 'cover_url': 'https://c'})  # 덮어쓰기
    row = repo.get_music_lookup(10)
    assert (row['status'], row['artist'], row['cover_url']) == ('found', 'IU', 'https://c')


def test_run_pending_records_results_and_waits_between_albums(audiobook_db, monkeypatch):
    provider = FakeProvider({'artist': 'IU', 'cover_url': 'https://c'})
    monkeypatch.setattr(lookup, '_music_lookup_providers', lambda: [provider])
    monkeypatch.setattr('services.system_health_service.SystemHealthService.record_success', lambda *a, **k: None)
    sleeps = []

    assert lookup.run_pending(sleep=sleeps.append) == 1
    assert sleeps == [lookup.LOOKUP_INTERVAL_SEC]
    assert lookup.get_found_lookup(10)['artist'] == 'IU'
    assert lookup.run_pending(sleep=sleeps.append) == 0   # 다시 묻지 않는다


def test_run_pending_records_nothing_without_a_provider(audiobook_db, monkeypatch):
    monkeypatch.setattr(lookup, '_music_lookup_providers', lambda: [])
    monkeypatch.setattr('services.system_health_service.SystemHealthService.record_success', lambda *a, **k: None)
    assert lookup.run_pending(sleep=lambda _s: None) == 0
    assert sqlite_repo.AudiobookRepository.get_music_lookup(10) is None   # 나중에 플러그인을 켜면 그때 조회
