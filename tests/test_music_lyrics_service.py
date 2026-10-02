"""음악 가사: album.yaml → 곡 파일 태그 순, LRC 파싱, 곡 ↔ album.yaml 항목 매칭."""
import os
import shutil

from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, USLT

from services import music_lyrics_service as lyrics
from services.audiobook_scanner import parse_audiobook_folder

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'music')

ALBUM_YAML = """\
code: YAG55823736
title: Andy The First New Dream
artist: 앤디
originally_available_at: '2008-01-17'
studio: ㈜티오피미디어
summary: '앤디의 새로운 꿈이&nbsp;시작된다!<br>두 번째 줄'
tracks:
  '1':
    '1':
      title: New Dream (Intro)
      lyrics: []
    '2':
      title: Love Song
      lyrics:
      - format: lrc
        data: "[00:07.09]첫 줄\\n[00:10.5]둘째 줄\\n[ar:앤디]"
"""


def _flac(dest, **tags):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(os.path.join(FIXTURES, 'silence.flac'), dest)
    audio = FLAC(dest)
    for key, value in tags.items():
        audio[key] = value
    audio.save()
    return dest


def test_lrc_lines_are_timed_sorted_and_metadata_tags_dropped():
    synced, lines = lyrics.parse_lyrics('[ar:가수]\n[00:10.50]둘\n[00:01.2][00:20.00]후렴\n머리말')
    assert synced is True
    assert lines == [{'t': 1.2, 'text': '후렴'}, {'t': 10.5, 'text': '둘'}, {'t': 20.0, 'text': '후렴'}]


def test_plain_text_lyrics_are_unsynced_and_trimmed():
    synced, lines = lyrics.parse_lyrics('\n\n첫 줄\r\n\r\n둘째 줄\n\n')
    assert synced is False
    assert [l['text'] for l in lines] == ['첫 줄', '', '둘째 줄']
    assert all(l['t'] is None for l in lines)


def test_album_yaml_lyrics_win_over_tags_and_are_matched_by_title(tmp_path):
    album = tmp_path / 'Andy'
    album.mkdir()
    (album / 'album.yaml').write_text(ALBUM_YAML, encoding='utf-8')
    song = _flac(str(album / '2.flac'), title='Love Song', lyrics='태그 가사')

    result = lyrics.get_track_lyrics(str(album), song, 'Love Song', 5, 9)  # 순서/곡 수가 달라도 제목으로 찾는다

    assert result['source'] == 'album_yaml' and result['synced'] is True
    assert [l['text'] for l in result['lines']] == ['첫 줄', '둘째 줄']


def test_tag_lyrics_are_used_when_album_yaml_has_none(tmp_path):
    album = tmp_path / 'Andy'
    album.mkdir()
    (album / 'album.yaml').write_text(ALBUM_YAML, encoding='utf-8')
    song = _flac(str(album / '1.flac'), title='New Dream (Intro)', lyrics='[00:02.00]태그 싱크 가사')

    result = lyrics.get_track_lyrics(str(album), song, 'New Dream (Intro)', 0, 2)

    assert result['source'] == 'tag'
    assert result['lines'] == [{'t': 2.0, 'text': '태그 싱크 가사'}]


def test_mp3_uslt_prefers_the_synced_frame(tmp_path):
    song = str(tmp_path / 'a.mp3')
    shutil.copyfile(os.path.join(FIXTURES, 'silence.mp3'), song)
    tags = ID3()
    tags.add(USLT(encoding=3, lang='eng', desc='', text='길고 긴 일반 가사 ' * 20))
    tags.add(USLT(encoding=3, lang='XXX', desc='', text='[00:07.09]싱크 가사'))
    tags.save(song)

    result = lyrics.get_track_lyrics(None, song, 'x', 0, 1)

    assert result['synced'] is True and result['lines'][0]['text'] == '싱크 가사'


def test_no_lyrics_anywhere(tmp_path):
    song = _flac(str(tmp_path / 'x' / '1.flac'), title='T')
    assert lyrics.get_track_lyrics(str(tmp_path / 'x'), song, 'T', 0, 1) == {'source': None, 'synced': False, 'lines': []}


def test_scanner_fills_album_info_from_album_yaml_but_keeps_the_folder_name_as_title(tmp_path):
    album = tmp_path / '[2008.01.17 정규앨범] Andy The First New Dream'
    album.mkdir()
    (album / 'album.yaml').write_text(ALBUM_YAML, encoding='utf-8')
    _flac(str(album / '01.flac'))                       # 태그 없음 → album.yaml 순서 제목
    _flac(str(album / '02.flac'), title='Love Song', artist='앤디')

    result = parse_audiobook_folder(str(album), music=True)
    meta = result['meta']

    assert meta['title'] == '[2008.01.17 정규앨범] Andy The First New Dream'
    assert (meta['author'], meta['premiered'], meta['publisher']) == ('앤디', '2008-01-17', '㈜티오피미디어')
    assert meta['description'] == '앤디의 새로운 꿈이 시작된다!\n두 번째 줄'
    assert [t['title'] for t in result['tracks']] == ['New Dream (Intro)', 'Love Song']


def test_audiobook_mode_ignores_album_yaml(tmp_path):
    book = tmp_path / 'Book'
    book.mkdir()
    (book / 'album.yaml').write_text(ALBUM_YAML, encoding='utf-8')
    _flac(str(book / '01.flac'))

    assert parse_audiobook_folder(str(book))['meta']['author'] == ''
