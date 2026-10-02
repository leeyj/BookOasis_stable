"""오디오북 세션 '음악' 속성 카테고리(음악 모드) 스캔 규칙.

폴더 = 앨범, 폴더 이름 = 제목. 태그는 곡 표시(제목/아티스트)에만 쓰고 앨범을 묶는 데는 쓰지 않는다.
"""
import os
import shutil
import sqlite3
from contextlib import contextmanager

import pytest
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3

from repositories.sqlite import audiobook_repository as sqlite_audiobook_repository
from services import audiobook_scanner
from services.audiobook_scanner import (
    music_title_from_filename,
    parse_audiobook_folder,
    read_embedded_cover,
    scan_audiobook_library,
)
from services.db_migration_service import _SCHEMA_SQL

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'music')
FAKE_JPEG = b'\xff\xd8\xff\xe0' + b'fake-front-cover'


def _copy(src_name, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(os.path.join(FIXTURES, src_name), dest)
    return dest


def _flac(dest, title=None, artist=None, album=None, picture=None):
    _copy('silence.flac', dest)
    audio = FLAC(dest)
    for key, value in (('title', title), ('artist', artist), ('album', album)):
        if value:
            audio[key] = value
    if picture:
        pic = Picture()
        pic.type = 3
        pic.mime = 'image/jpeg'
        pic.data = picture
        audio.add_picture(pic)
    audio.save()
    return dest


def _mp3(dest, title=None, artist=None, picture=None):
    _copy('silence.mp3', dest)
    if title or artist:
        tags = EasyID3()
        if title:
            tags['title'] = title
        if artist:
            tags['artist'] = artist
        tags.save(dest)
    if picture:
        id3 = ID3(dest) if (title or artist) else ID3()
        id3.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='', data=picture))
        id3.save(dest)
    return dest


@pytest.mark.parametrize('filename, expected', [
    ('001 아이유 - 밤편지.flac', ('밤편지', '아이유')),
    ('01. Intro.mp3', ('Intro', None)),
    ('1-03 Song Name.flac', ('Song Name', None)),
    ('[002] 노래.mp3', ('노래', None)),
    ('Love Attack.flac', ('Love Attack', None)),
])
def test_title_and_artist_come_from_the_filename_when_tags_are_missing(filename, expected):
    assert music_title_from_filename(filename) == expected


def test_a_chart_compilation_keeps_its_folder_name_instead_of_the_first_song_tags(tmp_path):
    album = tmp_path / '[멜론] 2026.08 월간 TOP 100 FLAC'
    _flac(str(album / '001 RESCENE - LOVE ATTACK.flac'), 'LOVE ATTACK', 'RESCENE', 'SCENEDROME')
    _flac(str(album / '002 아이오아이 - 갑자기.flac'), '갑자기', '아이오아이', 'miss me?')
    _mp3(str(album / '003 무명 - 태그없는곡.mp3'))

    result = parse_audiobook_folder(str(album), music=True)

    assert result['meta']['title'] == '[멜론] 2026.08 월간 TOP 100 FLAC'
    assert result['meta']['author'] == ''  # 아티스트가 제각각인 모음집은 앨범 아티스트를 비워 둔다
    assert [(t['title'], t['artist']) for t in result['tracks']] == [
        ('LOVE ATTACK', 'RESCENE'), ('갑자기', '아이오아이'), ('태그없는곡', '무명'),
    ]
    assert [t['track_number'] for t in result['tracks']] == [1, 2, 3]


def test_album_artist_is_taken_from_the_tracks_when_most_share_one(tmp_path):
    album = tmp_path / 'Palette'
    _flac(str(album / '01.flac'), 'Palette', '아이유')
    _flac(str(album / '02.flac'), '이름에게', '아이유')
    _flac(str(album / '03.flac'), 'Ending Scene', 'Guest')

    assert parse_audiobook_folder(str(album), music=True)['meta']['author'] == '아이유'


def test_a_dash_in_the_album_folder_name_is_not_split_into_artist_and_title(tmp_path):
    # 실제 사례: '[2018.12.24 싱글EP] A'NDY to Z - 선호하다' 가 저자/제목으로 잘못 쪼개졌다
    album = tmp_path / "[2018.12.24 싱글EP] A'NDY to Z - 선호하다"
    _flac(str(album / '01.flac'), '한잔 더 할까', '앤디')

    meta = parse_audiobook_folder(str(album), music=True)['meta']
    assert (meta['author'], meta['title']) == ('앤디', "[2018.12.24 싱글EP] A'NDY to Z - 선호하다")


def test_disc_folders_play_in_disc_order_not_interleaved(tmp_path):
    album = tmp_path / 'Artist - Double Album'
    _flac(str(album / 'CD2' / '01.flac'), 'Disc2 Track1', 'Artist')
    _flac(str(album / 'CD1' / '02.flac'), 'Disc1 Track2', 'Artist')
    _flac(str(album / 'CD1' / '01.flac'), 'Disc1 Track1', 'Artist')

    result = parse_audiobook_folder(str(album), music=True)

    assert [t['title'] for t in result['tracks']] == ['Disc1 Track1', 'Disc1 Track2', 'Disc2 Track1']


def test_album_without_folder_image_uses_the_first_track_as_cover_source(tmp_path):
    album = tmp_path / 'No Image Album'
    first = _flac(str(album / '01.flac'), 'One', 'A', picture=FAKE_JPEG)
    _flac(str(album / '02.flac'), 'Two', 'A')

    assert parse_audiobook_folder(str(album), music=True)['meta']['poster'] == os.path.normpath(first)


def test_folder_image_still_wins_over_embedded_art(tmp_path):
    album = tmp_path / 'With Image'
    _flac(str(album / '01.flac'), 'One', 'A', picture=FAKE_JPEG)
    (album / 'cover.jpg').write_bytes(FAKE_JPEG)

    assert parse_audiobook_folder(str(album), music=True)['meta']['poster'] == os.path.join(str(album), 'cover.jpg')


def test_audiobook_mode_is_unchanged(tmp_path):
    book = tmp_path / '저자 - 책'
    _flac(str(book / '01.flac'), 'Chapter', 'Narrator')

    result = parse_audiobook_folder(str(book))

    assert 'title' not in result['tracks'][0] and 'artist' not in result['tracks'][0]
    assert result['meta']['poster'] == ''
    assert (result['meta']['author'], result['meta']['title']) == ('저자', '책')


def test_unchanged_tracks_reuse_cached_tags_without_reopening_the_file(tmp_path, monkeypatch):
    album = tmp_path / 'Cached'
    path = _flac(str(album / '01.flac'), 'Fresh', 'Tag')
    stat = os.stat(path)
    cache = {os.path.normpath(path): {
        'file_size': stat.st_size, 'file_mtime': stat.st_mtime, 'duration': 0.5,
        'title': 'Cached Title', 'artist': 'Cached Artist',
    }}

    def fail(*_a, **_k):
        raise AssertionError('cached track must not be re-read')

    monkeypatch.setattr(audiobook_scanner, 'read_music_tags', fail)
    monkeypatch.setattr(audiobook_scanner, '_probe_music_duration_and_tags', fail)

    track = parse_audiobook_folder(str(album), existing_track_cache=cache, music=True)['tracks'][0]
    assert (track['title'], track['artist']) == ('Cached Title', 'Cached Artist')


def test_cached_audiobook_tracks_without_a_title_get_their_tags_read_once(tmp_path):
    album = tmp_path / 'Switched To Music'
    path = _flac(str(album / '01.flac'), 'Real Title', 'Real Artist')
    stat = os.stat(path)
    cache = {os.path.normpath(path): {
        'file_size': stat.st_size, 'file_mtime': stat.st_mtime, 'duration': 0.5, 'title': None, 'artist': None,
    }}

    track = parse_audiobook_folder(str(album), existing_track_cache=cache, music=True)['tracks'][0]
    assert (track['title'], track['artist']) == ('Real Title', 'Real Artist')


def test_embedded_cover_is_read_from_flac_and_mp3(tmp_path):
    assert read_embedded_cover(_flac(str(tmp_path / 'a.flac'), 'T', 'A', picture=FAKE_JPEG)) == FAKE_JPEG
    assert read_embedded_cover(_mp3(str(tmp_path / 'b.mp3'), 'T', 'A', picture=FAKE_JPEG)) == FAKE_JPEG
    assert read_embedded_cover(_flac(str(tmp_path / 'c.flac'), 'T', 'A')) is None


def test_library_scan_treats_a_folder_of_disc_folders_as_one_album(tmp_path, monkeypatch):
    root = tmp_path / 'MUSIC'
    _flac(str(root / 'Artist' / 'Double' / 'CD1' / '01.flac'), 'a', 'b')
    _flac(str(root / 'Artist' / 'Double' / 'Disc 2' / '01.flac'), 'c', 'd')
    _flac(str(root / 'Artist' / 'Single' / '01.flac'), 'e', 'f')
    calls = []

    monkeypatch.setattr('services.category_service.CategoryService.is_music_library', lambda _lid: True)
    monkeypatch.setattr('repositories.audiobook_repository.AudiobookRepository.get_folder_paths', lambda _lid: [])
    monkeypatch.setattr(audiobook_scanner, '_dispatch_audiobook_new_items_events', lambda *_a: None)

    def fake_save(folder, library_id=None, music=None):
        calls.append((os.path.relpath(folder, root), music))
        return len(calls)

    monkeypatch.setattr(audiobook_scanner, 'scan_and_save_audiobook_folder', fake_save)
    monkeypatch.setattr('repositories.audiobook_repository.AudiobookRepository.get_audiobook_by_id', lambda _aid: None)

    scan_audiobook_library(str(root), library_id=7)

    assert sorted(calls) == [(os.path.join('Artist', 'Double'), True), (os.path.join('Artist', 'Single'), True)]


def test_audiobook_library_scan_does_not_merge_disc_folders(tmp_path, monkeypatch):
    root = tmp_path / 'BOOKS'
    _flac(str(root / 'Book' / 'CD1' / '01.flac'))
    calls = []
    monkeypatch.setattr('services.category_service.CategoryService.is_music_library', lambda _lid: False)
    monkeypatch.setattr('repositories.audiobook_repository.AudiobookRepository.get_folder_paths', lambda _lid: [])
    monkeypatch.setattr(audiobook_scanner, '_dispatch_audiobook_new_items_events', lambda *_a: None)
    monkeypatch.setattr('repositories.audiobook_repository.AudiobookRepository.get_audiobook_by_id', lambda _aid: None)
    monkeypatch.setattr(audiobook_scanner, 'scan_and_save_audiobook_folder',
                        lambda folder, library_id=None, music=None: calls.append(os.path.relpath(folder, root)) or 1)

    scan_audiobook_library(str(root), library_id=7)

    assert calls == [os.path.join('Book', 'CD1')]


def test_cover_cache_extracts_embedded_art_and_remembers_albums_without_art(tmp_path, monkeypatch):
    from utils import cover_helper

    monkeypatch.setattr('services.cover_storage_service.get_covers_dir', lambda: str(tmp_path / 'covers'))
    with_art = _flac(str(tmp_path / 'art' / '01.flac'), 'T', 'A', picture=b'jpeg')
    without_art = _flac(str(tmp_path / 'noart' / '01.flac'), 'T', 'A')

    saved = []
    monkeypatch.setattr('tools.scanner.cover.save_as_thumbnail_webp', lambda _img, path: saved.append(path))
    opened = []

    class FakeImage:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr('PIL.Image.open', lambda buf: opened.append(buf.read()) or FakeImage())

    assert cover_helper.get_or_cache_remote_poster_webp(with_art, 'audio', library_id=1) == saved[0]
    assert opened == [b'jpeg']

    reads = []
    real_read = audiobook_scanner.read_embedded_cover
    monkeypatch.setattr(audiobook_scanner, 'read_embedded_cover', lambda p: reads.append(p) or real_read(p))
    assert cover_helper.get_or_cache_remote_poster_webp(without_art, 'audio', library_id=1) is None
    assert cover_helper.get_or_cache_remote_poster_webp(without_art, 'audio', library_id=1) is None
    assert reads == [without_art]


class _NonClosing:
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


def test_sqlite_update_track_tags_only_touches_changed_rows(monkeypatch):
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    connection.execute("INSERT INTO audiobooks (id, title, folder_name, folder_path) VALUES (1, 'A', 'A', '/m/A')")
    for n in (1, 2):
        connection.execute(
            "INSERT INTO audiobook_tracks (audiobook_id, track_number, filename, file_path) VALUES (1, ?, ?, ?)",
            (n, f'{n}', os.path.normpath(f'/m/A/{n}.flac')))
    wrapper = _NonClosing(connection)

    @contextmanager
    def fake_connection(_db_type):
        yield wrapper

    monkeypatch.setattr(sqlite_audiobook_repository.database, 'connection', fake_connection)
    repo = sqlite_audiobook_repository.AudiobookRepository
    tracks = [{'file_path': '/m/A/1.flac', 'title': 'One', 'artist': 'X'},
              {'file_path': '/m/A/2.flac', 'title': 'Two', 'artist': None}]

    assert repo.update_track_tags(1, tracks) == 2
    assert repo.update_track_tags(1, tracks) == 0
    rows = connection.execute('SELECT title, artist FROM audiobook_tracks ORDER BY track_number').fetchall()
    assert [tuple(r) for r in rows] == [('One', 'X'), ('Two', None)]


def test_nul_characters_left_by_taggers_are_removed(tmp_path):
    album = tmp_path / 'Olivia Ong - Just For You'
    _flac(str(album / '01.flac'), 'Just For You\x00', 'Olivia Ong\x00')
    _flac(str(album / '02.flac'), 'Fly Me\x00To The Moon', 'Olivia Ong')

    result = parse_audiobook_folder(str(album), music=True)

    assert result['meta']['author'] == 'Olivia Ong'
    assert [(t['title'], t['artist']) for t in result['tracks']] == [('Just For You', 'Olivia Ong'), ('Fly Me', 'Olivia Ong')]
