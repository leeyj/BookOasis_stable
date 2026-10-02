"""FLAC 스트리밍: 재생용 최소 헤더(STREAMINFO/SEEKTABLE) + 원본 오디오 프레임으로 보낸다.

실제 사례: 멜론 차트 FLAC의 PICTURE 블록이 깨져 있어 Chrome이 DEMUXER_ERROR_COULD_NOT_OPEN으로
파일을 열지 못했다. 태그/아트 블록을 빼고 보내면 같은 파일이 정상 재생된다.
"""
import io
import os
import shutil

import pytest
from flask import Flask
from mutagen.flac import FLAC, Picture

from api.routes import audiobook_routes
from api.routes.audiobook_routes import _flac_clean_layout, _send_audio_range_response

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'music')


def _blocks(data):
    assert data[:4] == b'fLaC'
    pos, blocks = 4, []
    while True:
        head = data[pos:pos + 4]
        length = int.from_bytes(head[1:4], 'big')
        blocks.append(head[0] & 0x7F)
        pos += 4 + length
        if head[0] & 0x80:
            return blocks, pos


def _tagged_flac(tmp_path, broken_picture=False):
    path = str(tmp_path / 'song.flac')
    shutil.copyfile(os.path.join(FIXTURES, 'silence.flac'), path)
    audio = FLAC(path)
    audio['title'] = 'Supernova'
    pic = Picture()
    pic.type = 3
    pic.mime = 'image/jpeg'
    pic.data = b'\xff\xd8' + b'x' * 5000
    audio.add_picture(pic)
    audio.save()
    if broken_picture:
        raw = bytearray(open(path, 'rb').read())
        _, frames = _blocks(bytes(raw))
        pos = 4
        while pos < frames:  # PICTURE 블록의 MIME 길이를 터무니없는 값으로 깨뜨린다
            length = int.from_bytes(raw[pos + 1:pos + 4], 'big')
            if raw[pos] & 0x7F == 6:
                raw[pos + 8:pos + 12] = (0x7FFFFFFF).to_bytes(4, 'big')
            pos += 4 + length
        open(path, 'wb').write(bytes(raw))
    return path


@pytest.fixture
def app(monkeypatch):
    audiobook_routes._FLAC_LAYOUT_CACHE.clear()
    monkeypatch.setattr(audiobook_routes, '_needs_audio_transcode', lambda *_a: (False, 0.0))
    return Flask(__name__)


def _virtual_stream(path):
    original = open(path, 'rb').read()
    header, frames_offset = _flac_clean_layout(path)
    return header + original[frames_offset:], original, frames_offset


@pytest.mark.parametrize('broken', [False, True])
def test_layout_keeps_only_streaminfo_and_seektable_and_the_same_audio_frames(tmp_path, broken):
    path = _tagged_flac(tmp_path, broken_picture=broken)
    virtual, original, frames_offset = _virtual_stream(path)

    original_blocks, original_frames = _blocks(original)
    assert 6 in original_blocks and 4 in original_blocks  # 원본엔 아트/태그가 있다
    blocks, frames = _blocks(virtual)
    assert set(blocks) <= {0, 3} and blocks[0] == 0
    assert virtual[frames:] == original[original_frames:]
    assert frames_offset == original_frames
    assert FLAC(io.BytesIO(virtual)).info.length == pytest.approx(0.5, abs=0.01)


def test_full_and_ranged_responses_serve_the_virtual_stream(tmp_path, app):
    path = _tagged_flac(tmp_path, broken_picture=True)
    virtual, _, _ = _virtual_stream(path)

    with app.test_request_context('/'):
        rv = _send_audio_range_response(path)
        assert rv.status_code == 200
        assert rv.headers['Content-Length'] == str(len(virtual))
        assert b''.join(rv.response) == virtual

    # 헤더와 프레임 경계를 가로지르는 구간 / 프레임 안쪽 구간 / 끝없는 구간
    _, frames = _blocks(virtual)
    assert frames + 10 < len(virtual)
    for start, end in ((10, frames + 5), (frames + 2, len(virtual) - 1), (0, None)):
        header = f'bytes={start}-' + ('' if end is None else str(end))
        with app.test_request_context('/', headers={'Range': header}):
            rv = _send_audio_range_response(path)
            stop = len(virtual) - 1 if end is None else end
            assert rv.status_code == 206
            assert rv.headers['Content-Range'] == f'bytes {start}-{stop}/{len(virtual)}'
            assert b''.join(rv.response) == virtual[start:stop + 1]


def test_non_flac_and_unparseable_flac_are_served_unchanged(tmp_path, app):
    mp3 = str(tmp_path / 'a.mp3')
    shutil.copyfile(os.path.join(FIXTURES, 'silence.mp3'), mp3)
    fake_flac = str(tmp_path / 'b.flac')
    open(fake_flac, 'wb').write(b'not a flac at all')

    for path in (mp3, fake_flac):
        original = open(path, 'rb').read()
        with app.test_request_context('/', headers={'Range': 'bytes=0-'}):
            rv = _send_audio_range_response(path)
            assert b''.join(rv.response) == original
