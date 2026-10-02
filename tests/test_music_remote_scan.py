"""원격(GDS 등 rclone) 음악 카테고리: 스캔은 곡 파일을 열지 않고, 재생할 때 채운다.

rclone VFS(cache-mode full, 256M read-chunk)는 태그만 읽어도 곡 파일 전체를 내려받는다(25MB FLAC 측정).
공유 드라이브 부담 때문에 스캔은 폴더 목록·크기·수정시각과 album.yaml만 쓴다.
"""
import os
import shutil

import pytest
from mutagen.flac import FLAC, Picture

from services import audiobook_scanner, music_enrich_service
from services.audiobook_scanner import parse_audiobook_folder

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'music')

ALBUM_YAML = """\
artist: 앤디
originally_available_at: '2009-10-27'
posters: 'https://image.example/55823736_600x600.JPG'
tracks:
  '1':
    '1': {title: Next Step (Intro)}
    '2': {title: Single Man}
"""


def _flac(dest, **tags):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(os.path.join(FIXTURES, 'silence.flac'), dest)
    picture = tags.pop('picture', None)
    audio = FLAC(dest)
    for key, value in tags.items():
        audio[key] = value
    if picture:
        pic = Picture()
        pic.type = 3
        pic.mime = 'image/jpeg'
        pic.data = picture
        audio.add_picture(pic)
    audio.save()
    return dest


@pytest.fixture
def no_audio_reads(monkeypatch):
    """곡 파일을 여는 모든 경로를 막는다 - 원격 음악 스캔에서 하나라도 불리면 실패."""
    def boom(*_a, **_k):
        raise AssertionError('remote music scan must not open audio files')

    for name in ('read_music_tags', '_probe_music_duration_and_tags', 'get_audio_duration_and_size',
                 'estimate_mp3_duration', 'read_embedded_cover'):
        monkeypatch.setattr(audiobook_scanner, name, boom)
    import mutagen
    monkeypatch.setattr(mutagen, 'File', boom)


def test_remote_music_scan_uses_album_yaml_and_never_opens_songs(tmp_path, no_audio_reads):
    album = tmp_path / '[2009.10.27 정규앨범] Single Man'
    album.mkdir()
    (album / 'album.yaml').write_text(ALBUM_YAML, encoding='utf-8')
    for name in ('01.flac', '02.flac'):
        (album / name).write_bytes(b'not really opened')

    result = parse_audiobook_folder(str(album), remote_fast_path=True, music=True)

    meta = result['meta']
    assert meta['title'] == '[2009.10.27 정규앨범] Single Man'
    assert (meta['author'], meta['premiered']) == ('앤디', '2009-10-27')
    assert meta['poster'] == 'https://image.example/55823736_600x600.JPG'   # 외부 URL - 공유 드라이브 요청 없음
    assert [(t['title'], t['duration']) for t in result['tracks']] == [('Next Step (Intro)', 0.0), ('Single Man', 0.0)]


def test_remote_chart_without_album_yaml_takes_titles_from_file_names(tmp_path, no_audio_reads):
    album = tmp_path / '[멜론] 2024.08 월간 TOP 100 FLAC'
    album.mkdir()
    (album / '001 aespa - Supernova.flac').write_bytes(b'x')
    (album / '002 (여자)아이들 - 클락션 (Klaxon).flac').write_bytes(b'x')
    (album / '003 NewJeans - How Sweet.flac').write_bytes(b'x')

    result = parse_audiobook_folder(str(album), remote_fast_path=True, music=True)

    assert [(t['title'], t['artist']) for t in result['tracks']] == [
        ('Supernova', 'aespa'), ('클락션 (Klaxon)', '(여자)아이들'), ('How Sweet', 'NewJeans')]
    assert result['meta']['poster'] == ''          # 내장 아트를 꺼내려 곡을 받지 않는다
    assert result['meta']['author'] == ''          # 모음집


def test_remote_folder_image_is_still_used(tmp_path, no_audio_reads):
    album = tmp_path / 'Olivia Ong - Just For You'
    (album / 'Disc 1').mkdir(parents=True)
    (album / 'Disc 1' / '01. It\'s Real.flac').write_bytes(b'x')
    (album / 'folder.jpg').write_bytes(b'\xff\xd8')

    meta = parse_audiobook_folder(str(album), remote_fast_path=True, music=True)['meta']
    assert meta['poster'] == os.path.join(str(album), 'folder.jpg')


def test_local_music_scan_still_reads_tags(tmp_path):
    album = tmp_path / 'Local'
    _flac(str(album / '01.flac'), title='Real Title', artist='Real Artist')
    track = parse_audiobook_folder(str(album), music=True)['tracks'][0]
    assert (track['title'], track['artist']) == ('Real Title', 'Real Artist')
    assert track['duration'] > 0


def test_rescanning_keeps_the_poster_filled_in_after_playback(tmp_path, monkeypatch):
    album = tmp_path / 'Chart'
    album.mkdir()
    song = album / '001 aespa - Supernova.flac'
    song.write_bytes(b'x')
    saved = {}

    class FakeRepo:
        @staticmethod
        def get_by_folder_path(_p):
            return {'id': 9, 'poster': os.path.normpath(str(song))}

        @staticmethod
        def get_audiobook_tracks(_aid):
            return []

        @staticmethod
        def save_audiobook_scan(folder, library_id, meta, tracks):
            saved['poster'] = meta['poster']
            return {'audiobook_id': 9, 'meta_updated': 0, 'track_inserts': 0, 'track_updates': 0, 'track_deletes': 0}

        @staticmethod
        def update_track_tags(_aid, _tracks):
            return 0

    monkeypatch.setattr('repositories.audiobook_repository.AudiobookRepository', FakeRepo)
    monkeypatch.setattr(audiobook_scanner, 'is_remote_path', lambda _p: True)

    assert audiobook_scanner.scan_and_save_audiobook_folder(str(album), library_id=None, music=True) == 9
    assert saved['poster'] == os.path.normpath(str(song))


# ---- 재생할 때 채우기 ----

class EnrichRepo:
    def __init__(self, track, album, tracks):
        self.track, self.album, self.tracks = track, album, tracks
        self.probe, self.refresh = None, None

    def get_track_by_id_and_audiobook_id(self, _tid, _aid):
        return self.track

    def update_track_probe(self, track_id, duration, title, artist):
        self.probe = (track_id, round(duration, 1), title, artist)
        self.track = {**self.track, 'duration': duration, 'artist': artist or self.track.get('artist')}
        self.tracks = [self.track]

    def get_audiobook_by_id(self, _aid):
        return self.album

    def get_audiobook_tracks(self, _aid):
        return self.tracks

    def refresh_enriched_album(self, audiobook_id, author=None, poster=None):
        self.refresh = (audiobook_id, author, poster)


def test_playing_a_song_fills_duration_tags_artist_and_poster(tmp_path, monkeypatch):
    path = _flac(str(tmp_path / 'Chart' / '001.flac'), title='Supernova', artist='aespa', picture=b'\xff\xd8art')
    repo = EnrichRepo({'id': 45, 'file_path': path, 'duration': 0.0, 'artist': None}, {'id': 9, 'author': '', 'poster': ''}, [])
    monkeypatch.setattr('repositories.audiobook_repository.AudiobookRepository', repo)

    assert music_enrich_service.enrich_track(9, 45) is True
    assert repo.probe == (45, 0.5, 'Supernova', 'aespa')
    assert repo.refresh == (9, 'aespa', os.path.normpath(path))


def test_tracks_that_already_have_a_duration_are_left_alone(monkeypatch):
    repo = EnrichRepo({'id': 1, 'file_path': '/x.flac', 'duration': 180.0}, {}, [])
    monkeypatch.setattr('repositories.audiobook_repository.AudiobookRepository', repo)
    assert music_enrich_service.enrich_track(1, 1) is False
    assert music_enrich_service.schedule_track_enrich(1, {'id': 1, 'duration': 180.0}) is False


def test_repeated_range_requests_schedule_one_enrichment(monkeypatch):
    runs = []
    monkeypatch.setattr(music_enrich_service, 'enrich_track', lambda aid, tid: runs.append((aid, tid)))
    row = {'id': 77, 'duration': 0}

    assert music_enrich_service.schedule_track_enrich(5, row, delay_sec=0.05) is True
    assert music_enrich_service.schedule_track_enrich(5, row, delay_sec=0.05) is False

    import time
    deadline = time.time() + 2
    while not runs and time.time() < deadline:
        time.sleep(0.01)
    time.sleep(0.05)
    assert runs == [(5, 77)]
    assert music_enrich_service.schedule_track_enrich(5, row, delay_sec=10) is True   # 끝나면 다시 예약 가능
