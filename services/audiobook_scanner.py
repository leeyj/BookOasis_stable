# -*- coding: utf-8 -*-
import os
import json
import re
import struct
import subprocess
import time
from utils.drive_helper import is_remote_path

AUDIO_EXTENSIONS = ('.mp3', '.m4b', '.m4a', '.flac', '.aac', '.wav', '.ogg', '.opus', '.wma')

_MP3_BITRATE_TABLE = {
    (3, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],   # MPEG1, Layer1
    (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],      # MPEG1, Layer2
    (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],       # MPEG1, Layer3
    (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],      # MPEG2, Layer1
    (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],           # MPEG2, Layer2
    (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],           # MPEG2, Layer3
    (0, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],      # MPEG2.5, Layer1
    (0, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],           # MPEG2.5, Layer2
    (0, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],           # MPEG2.5, Layer3
}

_MP3_SAMPLE_RATE_TABLE = {
    3: [44100, 48000, 32000],  # MPEG1
    2: [22050, 24000, 16000],  # MPEG2
    0: [11025, 12000, 8000],   # MPEG2.5
}

_LAYER_SAMPLES = {
    (3, 3): 384,   # MPEG1, Layer1
    (2, 3): 384,   # MPEG2/2.5, Layer1
    (3, 2): 1152,  # MPEG1, Layer2
    (2, 2): 1152,  # MPEG2/2.5, Layer2
    (3, 1): 1152,  # MPEG1, Layer3
    (2, 1): 576,   # MPEG2/2.5, Layer3
}


def natural_sort_key(s):
    """
    파일명/트랙명을 자연스러운 순서로 정렬하기 위한 키 함수.
    예: '01.mp3', '1A.mp3', '1B.mp3', '02.mp3', '10.mp3'
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


# ── 음악 모드(오디오북 세션의 '음악' 속성 카테고리) ─────────────────────────────
# 폴더 = 앨범, 폴더 이름 = 제목은 오디오북과 같다. 태그는 앨범을 묶는 데 쓰지 않고 곡 표시(제목/아티스트)에만 쓴다.
_DISC_DIR_RE = re.compile(r'^(?:cd|disc|disk)\s*[-_.]?\s*\d{1,2}$', re.IGNORECASE)
# '001 ', '01. ', '1-03 ', '[001] ' 같은 트랙 번호 접두어 (태그가 없을 때 파일명에서 떼어낸다)
_MUSIC_TRACK_PREFIX_RE = re.compile(
    r'^\s*(?:\[\s*\d+\s*\]\s*|\d{1,2}-\d{1,3}(?:\s*[.\-_)]\s*|\s+)|\d{1,3}\s*[.\-_)]\s*|\d{2,3}\s+)'
)


def is_disc_dir(name):
    """'CD1', 'Disc 2', 'disk-03' 처럼 한 앨범의 디스크를 나눈 하위 폴더인지."""
    return bool(_DISC_DIR_RE.match(str(name or '').strip()))


def _first_tag(tags, *keys):
    if not tags:
        return None
    for key in keys:
        try:
            value = tags.get(key)
        except Exception:
            value = None
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        # 일부 태그 도구가 남기는 NUL(값 끝 종결자, ID3v2.4 다중 값 구분자)은 첫 값만 남기고 정리
        text = str(value).split('\x00')[0].strip() if value is not None else ''
        if text:
            return text
    return None


def _tags_title_artist(tags):
    return _first_tag(tags, 'title', 'Title', 'TITLE'), _first_tag(tags, 'artist', 'Author', 'ARTIST')


def read_music_tags(file_path):
    """곡 태그에서 (제목, 아티스트)를 읽는다. 태그 영역만 읽어 원격(rclone)에서도 가볍게 유지한다."""
    try:
        if file_path.lower().endswith('.mp3'):
            from mutagen.easyid3 import EasyID3
            return _tags_title_artist(EasyID3(file_path))
        import mutagen
        audio = mutagen.File(file_path, easy=True)
        return _tags_title_artist(audio.tags if audio is not None else None)
    except Exception:
        return None, None


def _probe_music_duration_and_tags(file_path):
    """mp3가 아닌 곡은 mutagen으로 한 번만 열어 재생시간과 태그를 함께 얻는다. 실패하면 (0.0, None)."""
    try:
        import mutagen
        audio = mutagen.File(file_path, easy=True)
        if audio is None or not getattr(audio, 'info', None):
            return 0.0, None
        return float(audio.info.length or 0.0), _tags_title_artist(audio.tags)
    except Exception:
        return 0.0, None


def _plain_text(value):
    """album.yaml 소개 등 HTML 조각이 섞인 문자열 → 일반 텍스트(&nbsp;·<br> 정리)."""
    import html
    text = re.sub(r'<br\s*/?>', '\n', str(value or ''), flags=re.IGNORECASE)
    text = html.unescape(re.sub(r'<[^>]+>', '', text)).replace('\xa0', ' ')
    return text.strip()


def music_title_from_filename(filename):
    """태그가 없을 때 파일명에서 (제목, 아티스트)를 만든다. 예: '001 아이유 - 밤편지.flac' -> ('밤편지', '아이유')."""
    stem = os.path.splitext(os.path.basename(str(filename)))[0]
    stripped = _MUSIC_TRACK_PREFIX_RE.sub('', stem, count=1).strip() or stem.strip()
    if ' - ' in stripped:
        artist, title = stripped.split(' - ', 1)
        if artist.strip() and title.strip():
            return title.strip(), artist.strip()
    return stripped, None


def read_embedded_cover(file_path):
    """곡 파일의 내장 앨범 아트(bytes)를 꺼낸다. 앞표지(type 3)를 우선하고, 없으면 None."""
    try:
        lower = file_path.lower()
        if lower.endswith('.mp3'):
            from mutagen.id3 import ID3
            pictures = ID3(file_path).getall('APIC')
            front = [p for p in pictures if getattr(p, 'type', None) == 3]
            return (front or pictures)[0].data if pictures else None
        import mutagen
        audio = mutagen.File(file_path)
        if audio is None:
            return None
        pictures = list(getattr(audio, 'pictures', None) or [])  # FLAC
        if pictures:
            front = [p for p in pictures if getattr(p, 'type', None) == 3]
            return (front or pictures)[0].data
        tags = audio.tags
        if tags is None:
            return None
        if hasattr(tags, 'getall'):  # ID3 계열 (예: AIFF/WAV 내장 ID3)
            apics = tags.getall('APIC')
            if apics:
                return apics[0].data
        covr = tags.get('covr') if hasattr(tags, 'get') else None  # MP4/M4A
        if covr:
            return bytes(covr[0])
        block = tags.get('metadata_block_picture') if hasattr(tags, 'get') else None  # Ogg Vorbis/Opus
        if block:
            import base64
            from mutagen.flac import Picture
            return Picture(base64.b64decode(block[0])).data
    except Exception:
        return None
    return None


def get_audio_duration_and_size(file_path, file_size=None, remote_fast_path=False):
    """
    오디오 파일의 duration(초 단위 float) 및 file_size(byte)를 구합니다.
    mutagen 모듈을 우선 사용하고, 없을 경우 MP3/오디오 헤더 분석 fallback을 적용합니다.
    """
    if file_size is None:
        try:
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        except Exception:
            file_size = 0
    duration = 0.0

    # MP3는 요청 정책에 따라 파일 전체 분석 라이브러리를 우회하고
    # 앞/뒤 버퍼 기반 헤더 분석만 사용합니다.
    if file_path.lower().endswith('.mp3'):
        return estimate_mp3_duration(file_path, file_size, remote_fast_path=remote_fast_path), file_size

    # 1. mutagen 사용 시도
    try:
        import mutagen
        audio = mutagen.File(file_path)
        if audio is not None and hasattr(audio, 'info') and audio.info:
            duration = float(audio.info.length)
            return duration, file_size
    except Exception:
        pass

    # 2. tinytag 사용 시도
    try:
        from tinytag import TinyTag
        tag = TinyTag.get(file_path)
        if tag and tag.duration:
            duration = float(tag.duration)
            return duration, file_size
    except Exception:
        pass

    # 3. 순수 Python MP3 Frame Header 분석 (Fallback)
    if file_path.lower().endswith('.mp3'):
        duration = estimate_mp3_duration(file_path, file_size)

    # 4. duration이 0.0으로 남으면 ffprobe를 사용한 직접 파일 열기 폴백을 시도합니다.
    if duration <= 0.0:
        ffprobe_duration = _probe_duration_with_ffprobe(file_path)
        if ffprobe_duration > 0.0:
            duration = ffprobe_duration

    return duration, file_size


def _probe_duration_with_ffprobe(file_path):
    """
    ffprobe를 사용해 파일을 직접 열어 duration을 확인합니다.
    ffprobe가 없거나 파싱 실패 시 0.0을 반환합니다.
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path,
        ]
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            return 0.0

        raw = (completed.stdout or '').strip()
        if not raw:
            return 0.0

        parsed = float(raw)
        if parsed > 0.0:
            return parsed
    except Exception:
        pass
    return 0.0


def estimate_mp3_duration(file_path, file_size, remote_fast_path=False):
    """
    mutagen/tinytag 패키지가 없을 때 MP3 파일의 기본 프레임 헤더를 파싱하여 duration을 가늠하는 순수 파이썬 fallback.
    """
    if file_size <= 0:
        return 0.0

    try:
        head_size = min(65536, file_size)
        tail_size = min(65536, file_size)

        with open(file_path, 'rb') as f:
            head = f.read(head_size)
            probe = b''
            probe_offset = 0

            id3v2_size = 0
            if head.startswith(b'ID3') and len(head) >= 10:
                tag_size = ((head[6] & 0x7F) << 21) | ((head[7] & 0x7F) << 14) | ((head[8] & 0x7F) << 7) | (head[9] & 0x7F)
                footer = 10 if (head[5] & 0x10) else 0
                id3v2_size = min(file_size, 10 + tag_size + footer)

                # ID3v2가 매우 큰 경우, 오디오 시작 오프셋 근처를 같은 파일 핸들에서 1회 추가 읽기
                if id3v2_size >= max(0, head_size - 4):
                    f.seek(id3v2_size)
                    probe_offset = id3v2_size
                    probe = f.read(8192)

            tail = b''
            if not remote_fast_path:
                f.seek(max(0, file_size - tail_size))
                tail = f.read(tail_size)

        # 뒷부분: ID3v1 존재 시 128바이트 제외
        id3v1_size = 0
        if tail and file_size >= 128 and tail[-128:-125] == b'TAG':
            id3v1_size = 128
        audio_size = max(0, file_size - id3v2_size - id3v1_size)

        frame_pos, frame = _find_first_mp3_frame(id3v2_size, head, probe_buf=probe, probe_offset=probe_offset)
        if not frame:
            # 첫 프레임을 못 잡으면 안전한 기본값으로 추정
            return (audio_size * 8) / (128 * 1000) if audio_size > 0 else 0.0

        # Xing/Info는 일반적으로 앞부분에 있으나, 요청에 맞춰 뒤쪽 버퍼에서도 함께 확인
        xing_frames = _extract_xing_frames(head)
        if xing_frames is None and not remote_fast_path:
            xing_frames = _extract_xing_frames(tail)
        if xing_frames and frame.get('samples_per_frame', 0) > 0 and frame.get('sample_rate', 0) > 0:
            return float(xing_frames * frame['samples_per_frame']) / float(frame['sample_rate'])

        kbps = frame.get('bitrate_kbps', 0)
        if kbps > 0:
            # CBR 추정: 앞/뒤 태그 영역을 제외한 오디오 본문 크기만 사용
            return (audio_size * 8) / (kbps * 1000)
    except Exception:
        pass

    # 기본 비트레이트 128kbps 가늠치
    return (file_size * 8) / (128 * 1000) if file_size > 0 else 0.0


def _parse_mp3_frame_header(header_bytes):
    if len(header_bytes) < 4:
        return None
    header = struct.unpack('>I', header_bytes[:4])[0]

    if ((header >> 21) & 0x7FF) != 0x7FF:
        return None

    version_id = (header >> 19) & 0x3
    layer_id = (header >> 17) & 0x3
    bitrate_idx = (header >> 12) & 0xF
    sample_idx = (header >> 10) & 0x3

    if version_id == 1 or layer_id == 0 or bitrate_idx in (0, 15) or sample_idx == 3:
        return None

    version_key = version_id
    layer_key = layer_id
    bitrate_table = _MP3_BITRATE_TABLE.get((version_key, layer_key))
    sample_table = _MP3_SAMPLE_RATE_TABLE.get(version_key)
    if not bitrate_table or not sample_table:
        return None

    bitrate_kbps = bitrate_table[bitrate_idx]
    sample_rate = sample_table[sample_idx]
    if bitrate_kbps <= 0 or sample_rate <= 0:
        return None

    samples_key_version = 3 if version_key == 3 else 2
    samples_per_frame = _LAYER_SAMPLES.get((samples_key_version, layer_key), 1152)

    return {
        'version_id': version_id,
        'layer_id': layer_id,
        'bitrate_kbps': bitrate_kbps,
        'sample_rate': sample_rate,
        'samples_per_frame': samples_per_frame,
    }


def _find_first_mp3_frame(start_offset, head_buf, probe_buf=None, probe_offset=0):
    scan_offset = min(max(0, start_offset), max(0, len(head_buf) - 4))

    for i in range(scan_offset, max(0, len(head_buf) - 4)):
        if head_buf[i] != 0xFF or (head_buf[i + 1] & 0xE0) != 0xE0:
            continue
        frame = _parse_mp3_frame_header(head_buf[i:i + 4])
        if frame:
            return i, frame

    chunk = probe_buf or b''
    for i in range(max(0, len(chunk) - 4)):
        if chunk[i] != 0xFF or (chunk[i + 1] & 0xE0) != 0xE0:
            continue
        frame = _parse_mp3_frame_header(chunk[i:i + 4])
        if frame:
            return probe_offset + i, frame

    return None, None


def _extract_xing_frames(buf):
    if not buf or len(buf) < 16:
        return None

    for marker in (b'Xing', b'Info'):
        idx = buf.find(marker)
        while idx != -1:
            flags_pos = idx + 4
            if flags_pos + 4 <= len(buf):
                flags = struct.unpack('>I', buf[flags_pos:flags_pos + 4])[0]
                pos = flags_pos + 4
                if flags & 0x1:
                    if pos + 4 <= len(buf):
                        frames = struct.unpack('>I', buf[pos:pos + 4])[0]
                        if frames > 0:
                            return frames
                    return None
            idx = buf.find(marker, idx + 1)

    return None


METADATA_JSON_COVER_KEYS = ('cover', 'poster')


def _base64_blob_payload(blob):
    if not isinstance(blob, dict) or str(blob.get('encoding', 'base64')).lower() != 'base64':
        return None
    payload = blob.get('data')
    return payload if isinstance(payload, str) and payload else None


def metadata_json_cover_blob(data):
    """metadata.json의 images.cover|poster → image_blobs[hash] 내장 표지(base64 문자열)를 돌려준다. 없으면 None.
    다운로더 버전에 따라 키가 cover/poster로 갈리고, 키가 없더라도 blob이 하나뿐이면 그것을 표지로 본다."""
    if not isinstance(data, dict):
        return None
    blobs = data.get('image_blobs')
    if not isinstance(blobs, dict):
        return None
    images = data.get('images')
    if isinstance(images, dict):
        for key in METADATA_JSON_COVER_KEYS:
            ref = images.get(key)
            payload = _base64_blob_payload(blobs.get(ref)) if isinstance(ref, str) else None
            if payload:
                return payload
    if len(blobs) == 1:
        return _base64_blob_payload(next(iter(blobs.values())))
    return None


def load_json_any_encoding(json_path):
    """사용자가 만든 json을 인코딩과 무관하게 읽는다: (data, encoding).
    json.loads(bytes)가 UTF-8(BOM 포함)/UTF-16/UTF-32를 판별하고, 그래도 안 되면 한글 윈도우 ANSI(cp949)로 다시 읽는다."""
    with open(json_path, 'rb') as f:
        raw = f.read()
    try:
        return json.loads(raw), 'utf'
    except UnicodeDecodeError:
        return json.loads(raw.decode('cp949')), 'cp949'


def read_metadata_json_cover(json_path, max_bytes=20 * 1024 * 1024):
    """metadata.json에 내장된 표지 이미지 바이트를 꺼낸다. 실패 시 None."""
    import base64
    try:
        if os.path.getsize(json_path) > max_bytes:
            return None
        payload = metadata_json_cover_blob(load_json_any_encoding(json_path)[0])
        return base64.b64decode(payload) if payload else None
    except Exception:
        return None


def parse_audiobook_folder(folder_path, existing_track_cache=None, remote_fast_path=False, music=False):
    """
    단일 오디오북 디렉터리를 분석하여 메타데이터 및 트랙 목록을 파싱합니다.
    music=True(음악 카테고리)면 디스크 하위 폴더 순서를 지키고, 곡 태그로 트랙 제목/아티스트를 채우며,
    폴더 이미지가 없을 때 첫 곡의 내장 아트를 커버로 쓴다(커버 캐시가 첫 요청 때 꺼낸다).

    음악 + 원격 마운트(remote_fast_path)면 곡 파일을 아예 열지 않는다. rclone VFS(cache-mode full, 큰
    read-chunk)는 태그만 읽어도 곡 파일 전체를 내려받아(25MB FLAC 측정: 25MB 전부) 공유 드라이브(GDS)에
    부담이 크기 때문이다. 이때 제목은 album.yaml → 파일명, 길이는 0(재생할 때 music_enrich_service가 채움),
    커버는 폴더 이미지 → album.yaml 포스터 URL 순이며 내장 아트는 쓰지 않는다.
    """
    skip_audio_reads = bool(music and remote_fast_path)
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return None

    folder_name = os.path.basename(os.path.normpath(folder_path))
    audio_files = []

    # 오디오 파일 검색 (하위 폴더까지 한 권으로 모은다)
    book_root = os.path.normpath(folder_path)
    nested_meta_dirs = set()
    for root, _, files in os.walk(folder_path):
        if os.path.normpath(root) != book_root and ('metadata.json' in files or 'audio.json' in files):
            nested_meta_dirs.add(os.path.relpath(root, book_root))
        for file in files:
            if file.lower().endswith(AUDIO_EXTENSIONS):
                full_path = os.path.normpath(os.path.join(root, file))
                audio_files.append(full_path)

    if not audio_files:
        return None

    # 이 폴더 자체에도 음원이 있는데 하위 폴더에도 음원이 있으면, 하위 폴더들이 따로 등록되지 않고
    # 이 책에 합쳐진다(라이브러리 스캔은 음원이 있는 폴더에서 더 내려가지 않는다). 알림센터로 알린다.
    nested_audio_dirs = sorted({os.path.relpath(os.path.dirname(p), book_root) for p in audio_files
                                if os.path.dirname(p) != book_root})
    has_own_audio = any(os.path.dirname(p) == book_root for p in audio_files)
    nested_audio = None
    if has_own_audio and nested_audio_dirs:
        nested_audio = {'dirs': nested_audio_dirs, 'meta_dirs': sorted(nested_meta_dirs)}

    # 트랙 파일 자연어 순서 정렬 (음악: CD1/01, CD2/01 이 섞이지 않게 하위 폴더 순서가 먼저)
    if music:
        album_root = os.path.normpath(folder_path)
        audio_files.sort(key=lambda p: (
            natural_sort_key(os.path.relpath(os.path.dirname(p), album_root)),
            natural_sort_key(os.path.basename(p)),
        ))
    else:
        audio_files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))

    # 메타데이터 준비 (`metadata.json` 또는 `audio.json` 우선 읽기)
    meta = {
        'title': '',
        'author': '',
        'publisher': '',
        'code': '',
        'web_id': '',
        'poster': '',
        'premiered': '',
        'ratings': 0.0,
        'author_intro': '',
        'description': '',
        'folder_name': folder_name,
        'folder_path': os.path.normpath(folder_path),
        'file_type': 'single' if len(audio_files) == 1 else 'multi'
    }

    metadata_json_path = os.path.join(folder_path, 'metadata.json')
    audio_json_path = os.path.join(folder_path, 'audio.json')
    metadata_track_durations = []
    metadata_has_cover_blob = False
    metadata_cover_b64 = None
    metadata_json_loaded = False

    if os.path.exists(metadata_json_path):
        try:
            data, json_encoding = load_json_any_encoding(metadata_json_path)
            if json_encoding != 'utf':
                print(f"[AudiobookScanner] metadata.json read as {json_encoding} (not UTF-8) in {folder_path}")
            if not isinstance(data, dict):
                raise ValueError('top-level JSON is not an object')
            metadata_json_loaded = True
            metadata_cover_b64 = metadata_json_cover_blob(data)
            metadata_has_cover_blob = metadata_cover_b64 is not None
            meta['title'] = str(data.get('title', '')).strip()
            meta['publisher'] = str(data.get('publisher', '')).strip()
            meta['description'] = str(data.get('description', '')).strip()
            meta['premiered'] = str(data.get('publishedDate', '') or data.get('publishedYear', '')).strip()
            meta['isbn'] = str(data.get('isbn', '')).strip()
            meta['web_id'] = str(data.get('web_id', '')).strip()

            authors_list = data.get('authors', [])
            narrators_list = data.get('narrators', [])
            author_str = ", ".join(str(a).strip() for a in authors_list if a) if isinstance(authors_list, list) else str(authors_list or '')
            if narrators_list and isinstance(narrators_list, list):
                narrator_str = ", ".join(str(n).strip() for n in narrators_list[:3] if n)
                if len(narrators_list) > 3:
                    narrator_str += " 등"
                author_str = f"{author_str} (낭독: {narrator_str})" if author_str else f"낭독: {narrator_str}"
            meta['author'] = author_str

            chapters = data.get('chapters', [])
            if isinstance(chapters, list):
                for chapter in chapters:
                    if not isinstance(chapter, dict):
                        continue
                    try:
                        start_sec = float(chapter.get('start', 0.0) or 0.0)
                        end_sec = float(chapter.get('end', 0.0) or 0.0)
                    except (TypeError, ValueError):
                        continue
                    if end_sec >= start_sec:
                        metadata_track_durations.append(end_sec - start_sec)
        except Exception as err:
            print(f"[AudiobookScanner Warning] metadata.json read error in {folder_path}: {err}")
    # metadata.json이 없거나 파싱에 실패하면 audio.json으로 폴백한다
    if not metadata_json_loaded and os.path.exists(audio_json_path):
        try:
            json_data, json_encoding = load_json_any_encoding(audio_json_path)
            if json_encoding != 'utf':
                print(f"[AudiobookScanner] audio.json read as {json_encoding} (not UTF-8) in {folder_path}")
            meta['title'] = str(json_data.get('title', '')).strip()
            meta['author'] = str(json_data.get('author', '')).strip()
            meta['publisher'] = str(json_data.get('publisher', '')).strip()
            meta['code'] = str(json_data.get('code', '')).strip()
            meta['web_id'] = str(json_data.get('web_id', '')).strip()
            meta['poster'] = str(json_data.get('poster', '')).strip()
            meta['premiered'] = str(json_data.get('premiered', '')).strip()
            meta['author_intro'] = str(json_data.get('author_intro', '')).strip()
            meta['description'] = str(json_data.get('desc', '') or json_data.get('description', '')).strip()
            try:
                meta['ratings'] = float(json_data.get('ratings', 0.0))
            except (ValueError, TypeError):
                meta['ratings'] = 0.0
        except Exception as err:
            print(f"[AudiobookScanner Warning] audio.json read error in {folder_path}: {err}")

    # 음악: album.yaml(앨범 정보·곡 제목·가사)이 있으면 쓴다. 제목은 폴더 이름 원칙 그대로 두고
    # 아티스트/발매일/레이블/소개만 채운다. 가사는 재생 시점에 music_lyrics_service가 읽는다.
    album_yaml_entries = []
    if music and not meta['author']:
        from services.music_lyrics_service import album_yaml_tracks, load_album_yaml
        album_yaml = load_album_yaml(folder_path)
        if album_yaml:
            meta['author'] = str(album_yaml.get('artist') or '').strip()
            meta['premiered'] = meta['premiered'] or str(album_yaml.get('originally_available_at') or '').strip()
            meta['publisher'] = meta['publisher'] or str(album_yaml.get('studio') or '').strip()
            meta['code'] = meta['code'] or str(album_yaml.get('code') or '').strip()
            meta['description'] = meta['description'] or _plain_text(album_yaml.get('summary'))
            album_yaml_entries = album_yaml_tracks(album_yaml)
            if not meta['poster']:
                posters = album_yaml.get('posters')
                poster_url = posters[0] if isinstance(posters, list) and posters else posters
                if isinstance(poster_url, str) and poster_url.startswith(('http://', 'https://')):
                    meta['poster'] = poster_url.strip()

    # 커버 포스터 이미지 자동 탐지 (poster.jpg, cover.jpg, folder.jpg 등 ➔ 없으면 *.jpg, *.jpeg, *.png, *.webp 탐지)
    if not meta['poster'] or not meta['poster'].startswith(('http://', 'https://')):
        poster_candidates = ['poster.jpg', 'cover.jpg', 'folder.jpg', 'poster.png', 'cover.png', 'folder.png', 'poster.jpeg', 'cover.jpeg', 'folder.jpeg']
        found_poster = None
        for cand in poster_candidates:
            cand_path = os.path.join(folder_path, cand)
            if os.path.exists(cand_path):
                found_poster = cand_path
                break

        # 알려진 이름이 없는 경우 폴더 내 첫 번째 *.jpg / *.jpeg / *.png / *.webp 이미지 파일 탐지
        if not found_poster and os.path.exists(folder_path):
            try:
                for file_name in os.listdir(folder_path):
                    if file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        found_poster = os.path.join(folder_path, file_name)
                        break
            except Exception:
                pass

        if found_poster:
            meta['poster'] = found_poster
        elif metadata_has_cover_blob:
            # 폴더 이미지가 없고 metadata.json에 표지가 내장(image_blobs)돼 있으면 json 경로를 포스터 소스로 둔다
            # (base64를 DB에 넣지 않고, 커버 캐시가 첫 요청 때 디코딩한다)
            meta['poster'] = os.path.normpath(metadata_json_path)
        elif music and not meta['poster'] and not skip_audio_reads:
            # 폴더 이미지가 없는 음악 앨범: 첫 곡 경로를 포스터 소스로 두면 커버 캐시가 내장 아트를 꺼낸다
            # (원격은 곡 파일 전체를 받게 되므로 하지 않는다 - album.yaml 포스터 URL 또는 재생 후 채움)
            meta['poster'] = os.path.normpath(audio_files[0])

    # audio.json / metadata.json에 title/author가 누락되었거나 없으면 폴더명 fallback ("저자 - 제목")
    # (음악은 앨범 이름에 ' - '가 흔해 쪼개지 않는다 — 폴더 이름 = 제목, 아티스트는 곡 태그 다수결)
    if music and not meta['title']:
        meta['title'] = folder_name
    if not meta['title'] or (not meta['author'] and not music):
        if ' - ' in folder_name:
            parts = folder_name.split(' - ', 1)
            if not meta['author']:
                meta['author'] = parts[0].strip()
            if not meta['title']:
                meta['title'] = parts[1].strip()
        else:
            if not meta['title']:
                meta['title'] = folder_name

    # 트랙 상세 정보 및 총 재생시간 계산
    tracks = []
    total_duration = 0.0
    duration_cache_hits = 0
    metadata_duration_hits = 0
    metadata_duration_fallbacks = 0
    file_probe_hits = 0
    track_cache = existing_track_cache or {}
    use_metadata_track_durations = len(metadata_track_durations) == len(audio_files) and len(audio_files) > 0
    verbose_track_log = str(os.environ.get('AUDIOBOOK_SCAN_VERBOSE', '')).strip().lower() in ('1', 'true', 'yes', 'on')

    for idx, fpath in enumerate(audio_files, start=1):
        normalized_path = os.path.normpath(fpath)
        try:
            stat_info = os.stat(fpath)
            file_size = int(stat_info.st_size)
            file_mtime = float(stat_info.st_mtime)
        except Exception:
            file_size = 0
            file_mtime = 0.0

        cache_row = track_cache.get(normalized_path)
        duration_source = 'file_probe'
        track_started_at = time.perf_counter()
        music_tags = None
        cache_hit = bool(
            cache_row and
            int(cache_row.get('file_size', -1)) == int(file_size) and
            int(float(cache_row.get('file_mtime', -1.0) or -1.0)) == int(file_mtime)
        )
        if cache_hit:
            duration = float(cache_row.get('duration', 0.0) or 0.0)
            duration_cache_hits += 1
            duration_source = 'cache'
            if music and cache_row.get('title'):
                music_tags = _tags_title_artist({'title': cache_row.get('title'), 'artist': cache_row.get('artist')})
        else:
            if use_metadata_track_durations:
                duration = float(metadata_track_durations[idx - 1] or 0.0)
                metadata_duration_hits += 1
                duration_source = 'metadata'
            elif remote_fast_path:
                # 원격(음악·오디오북 공통): 파일을 열지 않는다. rclone VFS는 길이만 읽어도 m4a 전체를 내려받아
                # (2026-10-11 측정: 9.4MiB m4a → 9.4MiB 전송, mp3도 파일당 ~252KB) 공유 드라이브 일일 전송량을
                # 소모한다. 길이는 재생할 때 이미 캐시된 파일에서 music_enrich_service가 채운다.
                duration = 0.0
                duration_source = 'deferred'
            else:
                duration = 0.0
                if music and not fpath.lower().endswith('.mp3'):
                    duration, music_tags = _probe_music_duration_and_tags(fpath)
                if duration <= 0.0:
                    duration, file_size = get_audio_duration_and_size(
                        fpath,
                        file_size=file_size,
                        remote_fast_path=remote_fast_path
                    )
                metadata_duration_fallbacks += 1
                file_probe_hits += 1
        if music and music_tags is None and not skip_audio_reads:
            music_tags = read_music_tags(fpath)

        if verbose_track_log:
            track_elapsed_ms = int((time.perf_counter() - track_started_at) * 1000)
            print(
                "[AudiobookScanner][TRACK_ANALYZED] "
                f"idx={idx} "
                f"source={duration_source} "
                f"duration_sec={float(duration or 0.0):.3f} "
                f"size={int(file_size or 0)} "
                f"mtime={int(float(file_mtime or 0.0))} "
                f"elapsed_ms={track_elapsed_ms} "
                f"path={normalized_path}"
            )

        total_duration += duration
        fname = os.path.basename(fpath)
        
        # [001] 등의 접두어를 정제한 깨끗한 트랙 타이틀
        clean_title = re.sub(r'^\s*\[\s*\d+\s*\]\s*', '', os.path.splitext(fname)[0]).strip()
        display_fname = clean_title if clean_title else fname

        code_match = re.search(r'(\d+[A-Za-z]?)', fname)
        track_code = code_match.group(1) if code_match else str(idx)

        ext = os.path.splitext(fname)[1].lstrip('.').lower()

        track = {
            'track_number': idx,
            'track_code': track_code,
            'filename': display_fname,
            'file_path': fpath,
            'file_mtime': file_mtime,
            'file_size': file_size,
            'duration': duration,
            'format': ext
        }
        if music:
            tag_title, tag_artist = music_tags or (None, None)
            name_title, name_artist = music_title_from_filename(fname)
            if not tag_title and len(album_yaml_entries) == len(audio_files):
                # 태그가 없으면 album.yaml의 같은 순서 곡 제목 (곡 수가 같을 때만)
                tag_title = str(album_yaml_entries[idx - 1].get('title') or '').strip() or None
            track['title'] = tag_title or name_title
            track['artist'] = tag_artist or (None if tag_title else name_artist)
        tracks.append(track)

    if music and not meta['author']:
        # 폴더명에 '아티스트 - 앨범'이 없으면 곡 아티스트가 절반 이상 같을 때만 앨범 아티스트로 쓴다(모음집은 비워 둠)
        from collections import Counter
        top = Counter(t['artist'] for t in tracks if t.get('artist')).most_common(1)
        if top and top[0][1] * 2 >= len(tracks):
            meta['author'] = top[0][0]

    meta['total_duration'] = total_duration
    meta['total_tracks'] = len(tracks)

    # 포스터가 metadata.json 내장 표지면, 이미 읽은 base64를 스캔 때 표지 캐시를 만드는 데 넘긴다(원본 재읽기 없음, 2.9.6)
    poster_preloaded_b64 = None
    if metadata_cover_b64 and meta.get('poster') == os.path.normpath(metadata_json_path):
        poster_preloaded_b64 = metadata_cover_b64

    return {
        'meta': meta,
        'tracks': tracks,
        'poster_preloaded_b64': poster_preloaded_b64,
        'duration_cache_hits': duration_cache_hits,
        'metadata_duration_hits': metadata_duration_hits,
        'metadata_duration_fallbacks': metadata_duration_fallbacks,
        'metadata_track_duration_mode': use_metadata_track_durations,
        'file_probe_hits': file_probe_hits,
        'nested_audio': nested_audio,
    }


def _touch_if_poster_replaced(repo, row_id, poster, category, library_id):
    """같은 경로의 표지 파일을 덮어쓴 경우(cover.jpg 교체) 경로가 같아 DB는 '변경 없음'이다.
    캐시가 그 원본보다 오래됐으면 updated_at을 올려 목록·상세 표지 주소(?t=)를 바꾼다(영상 스캐너도 사용)."""
    try:
        from utils.cover_helper import poster_cache_outdated
        if row_id and poster_cache_outdated(poster, category, library_id):
            repo.touch_updated_at(row_id)
    except Exception as e:
        print(f"[CoverRefresh] poster change check failed ({poster}): {e}")


def _cache_poster_for_scan(poster, library_id, folder_path, result, remote_fast_path):
    """스캔 때 표지 캐시를 만든다(2.9.6 - 예전엔 화면에서 처음 볼 때 만들어 첫 목록이 느렸다). (상태, ms)
    - metadata.json 내장 표지: 파싱 때 읽은 base64를 그대로 써서 원본을 다시 읽지 않는다
    - 폴더 이미지(cover.jpg 등): 작은 파일 하나를 읽는다(원격 포함)
    - 원격의 곡 파일 내장 아트: 건너뛴다(태그만 읽어도 곡 전체를 받게 됨 - 첫 요청 때 생성)
    - URL 포스터: 건너뛴다(외부 네트워크 - 첫 요청 때 생성)"""
    import base64
    started = time.perf_counter()
    if not poster or (remote_fast_path and str(poster).lower().endswith(AUDIO_EXTENSIONS)):
        return 'skipped', 0
    from utils.cover_helper import cache_poster_at_scan
    preloaded = None
    b64 = (result or {}).get('poster_preloaded_b64')
    json_path = os.path.normpath(os.path.join(folder_path, 'metadata.json'))
    if b64 and os.path.normpath(str(poster)) == json_path:
        try:
            if os.path.getsize(json_path) <= 20 * 1024 * 1024:  # read_metadata_json_cover와 같은 상한
                preloaded = base64.b64decode(b64)
        except Exception:
            preloaded = None
    state = cache_poster_at_scan(poster, 'audio', library_id, preloaded_bytes=preloaded)
    return state, int((time.perf_counter() - started) * 1000)


CODE_NESTED_AUDIO = 'audiobook_nested_audio'
CODE_SAVE_FAILED = 'audiobook_save_failed'


def _library_root_paths(library_id):
    if not library_id:
        return set()
    try:
        from repositories.category_repository import CategoryRepository
        lib = CategoryRepository.get_library_by_id('audiobook', library_id) or {}
        return {os.path.normpath(p.strip()) for p in str(lib.get('physical_path') or '').replace('\r', '').split('\n') if p.strip()}
    except Exception:
        return set()


def _report_nested_audio(audiobook_id, library_id, folder_path, title, nested_audio):
    """하위 폴더 음원이 한 권으로 합쳐진 책을 알림센터에 올리거나(있을 때), 해제한다(없어졌을 때).
    자동으로 고치지 않는다 - 안내는 카드 문구(음원을 옮긴 뒤 카테고리를 다시 등록)에 있다."""
    from services.problem_service import ProblemService, SEVERITY_ACTION_REQUIRED, SEVERITY_NOTICE, make_series_key
    target_id = f'ab:{audiobook_id}'  # 숫자가 아니어야 카드에 도서 단위 재스캔 버튼이 붙지 않는다
    if not nested_audio:
        ProblemService.resolve(CODE_NESTED_AUDIO, 'book', target_id, db_type='audiobook')
        return
    is_library_root = os.path.normpath(folder_path) in _library_root_paths(library_id)
    meta_dirs = set(nested_audio.get('meta_dirs') or [])
    dirs = nested_audio['dirs']
    shown = [d + (' [metadata.json]' if d in meta_dirs else '') for d in dirs[:8]]
    detail = ', '.join(shown) + (f' +{len(dirs) - 8}' if len(dirs) > 8 else '')
    ProblemService.report(
        CODE_NESTED_AUDIO, 'book', target_id, db_type='audiobook', library_id=library_id,
        severity=SEVERITY_ACTION_REQUIRED if (is_library_root or meta_dirs) else SEVERITY_NOTICE,
        target_path=os.path.normpath(folder_path), series_key=make_series_key(library_id, title),
        title=title, detail=detail,
        context={'library_root': is_library_root, 'nested_dirs': len(dirs), 'ignored_metadata_dirs': sorted(meta_dirs)[:20]},
    )


def scan_and_save_audiobook_folder(folder_path, library_id=None, music=None):
    """
    단일 오디오북 폴더를 스캔하여 오디오북 DB에 저장/업데이트합니다.
    music=None이면 카테고리 속성으로 음악 모드 여부를 판단한다(라이브러리 스캔은 한 번 판단해 넘겨준다).
    """
    from repositories.audiobook_repository import AudiobookRepository

    started_at = time.perf_counter()
    parse_elapsed_sec = 0.0

    try:
        normalized_folder_path = os.path.normpath(folder_path)
        remote_fast_path = is_remote_path(normalized_folder_path)

        # library_id 유효성 확인 (libraries 테이블에 존재하는지 체크, 없으면 None)
        if library_id is not None:
            from repositories.category_repository import CategoryRepository
            if not CategoryRepository.get_library_by_id('audiobook', library_id):
                library_id = None
        if music is None:
            from services.category_service import CategoryService
            music = CategoryService.is_music_library(library_id)

        # 기존 오디오북/트랙 정보로 파싱 시 duration 캐시 재사용을 위해 조회
        existing = AudiobookRepository.get_by_folder_path(normalized_folder_path)
        existing_track_cache = {}
        if existing:
            for r in AudiobookRepository.get_audiobook_tracks(existing['id']):
                if not r or not r.get('file_path'):
                    continue
                key = os.path.normpath(str(r['file_path']))
                existing_track_cache[key] = {
                    'file_mtime': float(r.get('file_mtime') or 0.0),
                    'file_size': int(r.get('file_size') or 0),
                    'duration': float(r.get('duration') or 0.0),
                    'title': r.get('title'),
                    'artist': r.get('artist')
                }

        if existing and existing_track_cache:
            _keep_renamed_track_ids(AudiobookRepository, existing['id'], normalized_folder_path, existing_track_cache)

        parse_started_at = time.perf_counter()
        result = parse_audiobook_folder(
            folder_path,
            existing_track_cache=existing_track_cache,
            remote_fast_path=remote_fast_path,
            music=music
        )
        parse_elapsed_sec = time.perf_counter() - parse_started_at
        if not result:
            return None

        meta = result['meta']
        tracks = result['tracks']
        if music and remote_fast_path and not meta.get('poster') and existing:
            kept = os.path.normpath(str(existing.get('poster') or ''))
            if existing.get('poster') and kept.startswith(normalized_folder_path + os.sep):
                meta['poster'] = kept
        if existing and int(existing.get('is_deleted') or 0):
            AudiobookRepository.set_deleted(existing['id'], False)
            print(f"[AudiobookScanner][RESTORED] audiobook_id={existing['id']} folder_path={normalized_folder_path}")
        if existing and int(existing.get('metadata_locked') or 0):
            # 상세 화면에서 수동 수정(잠금)한 책: 저자/출판사/소개/식별자/표지는 재스캔이 덮지 않는다 (트랙은 계속 갱신)
            for key in ('author', 'publisher', 'description', 'web_id', 'poster'):
                meta[key] = existing.get(key) or ''
        duration_cache_hits = int(result.get('duration_cache_hits', 0) or 0)
        metadata_duration_hits = int(result.get('metadata_duration_hits', 0) or 0)
        metadata_duration_fallbacks = int(result.get('metadata_duration_fallbacks', 0) or 0)
        metadata_track_duration_mode = bool(result.get('metadata_track_duration_mode', False))
        file_probe_hits = int(result.get('file_probe_hits', 0) or 0)

        scan_result = AudiobookRepository.save_audiobook_scan(normalized_folder_path, library_id, meta, tracks)
        audiobook_id = scan_result['audiobook_id']
        meta_updated = scan_result['meta_updated']
        track_inserts = scan_result['track_inserts']
        track_updates = scan_result['track_updates']
        track_deletes = scan_result['track_deletes']
        if music:
            track_updates += AudiobookRepository.update_track_tags(audiobook_id, tracks)
        _report_nested_audio(audiobook_id, library_id, normalized_folder_path, meta['title'], result.get('nested_audio'))
        _touch_if_poster_replaced(AudiobookRepository, audiobook_id, meta.get('poster'), 'audio', library_id)
        cover_cache_state, cover_elapsed_ms = _cache_poster_for_scan(
            meta.get('poster'), library_id, normalized_folder_path, result, remote_fast_path)
        from services.problem_service import ProblemService
        from services.scan_problem_service import _path_target_id
        ProblemService.resolve(CODE_SAVE_FAILED, 'book', _path_target_id(normalized_folder_path), db_type='audiobook')
        # 하위 폴더가 이 책에 합쳐졌으면 그 폴더들은 더 이상 따로 저장되지 않는다 - 예전 실패 기록도 닫는다
        for rel in (result.get('nested_audio') or {}).get('dirs') or []:
            ProblemService.resolve(CODE_SAVE_FAILED, 'book', _path_target_id(os.path.normpath(os.path.join(normalized_folder_path, rel))), db_type='audiobook')

        elapsed_sec = time.perf_counter() - started_at
        elapsed_ms = int(elapsed_sec * 1000)
        parse_elapsed_ms = int(parse_elapsed_sec * 1000)
        db_elapsed_sec = max(0.0, elapsed_sec - parse_elapsed_sec)
        db_elapsed_ms = int(db_elapsed_sec * 1000)

        duration_resolution_mode = 'mixed'
        if len(tracks) > 0 and duration_cache_hits == len(tracks) and metadata_duration_hits == 0 and file_probe_hits == 0:
            duration_resolution_mode = 'cache_only'
        elif file_probe_hits > 0 and metadata_duration_hits == 0 and duration_cache_hits == 0:
            duration_resolution_mode = 'file_probe_only'
        elif metadata_duration_hits > 0 and file_probe_hits == 0 and duration_cache_hits == 0:
            duration_resolution_mode = 'metadata_only'
        elif file_probe_hits > 0:
            duration_resolution_mode = 'probe_mixed'
        elif metadata_duration_hits > 0:
            duration_resolution_mode = 'metadata_mixed'
        elif duration_cache_hits > 0:
            duration_resolution_mode = 'cache_mixed'

        db_changed = (meta_updated + track_inserts + track_updates + track_deletes) > 0
        db_change_mode = 'changed' if db_changed else 'unchanged'
        scan_workload = 'cache_verify' if (duration_resolution_mode == 'cache_only' and not db_changed) else 'normal'

        print(
            "[AudiobookScanner][BOOK_PROCESSED] "
            f"audiobook_id={audiobook_id} "
            f"title={meta['title']} "
            f"tracks={len(tracks)} "
            f"timing_scope=single_folder "
            f"scan_workload={scan_workload} "
            f"duration_resolution_mode={duration_resolution_mode} "
            f"db_change_mode={db_change_mode} "
            f"remote_fast_path={remote_fast_path} "
            f"duration_cache_hits={duration_cache_hits} "
            f"metadata_track_duration_mode={metadata_track_duration_mode} "
            f"metadata_duration_hits={metadata_duration_hits} "
            f"metadata_duration_fallbacks={metadata_duration_fallbacks} "
            f"file_probe_hits={file_probe_hits} "
            f"db_meta_updated={meta_updated} "
            f"db_track_inserted={track_inserts} "
            f"db_track_updated={track_updates} "
            f"db_track_deleted={track_deletes} "
            f"cover_cache={cover_cache_state} "
            f"cover_elapsed_ms={cover_elapsed_ms} "
            f"duration_sec={meta['total_duration']:.1f} "
            f"parse_elapsed_sec={parse_elapsed_sec:.3f} "
            f"parse_elapsed_ms={parse_elapsed_ms} "
            f"db_elapsed_sec={db_elapsed_sec:.3f} "
            f"db_elapsed_ms={db_elapsed_ms} "
            f"elapsed_sec={elapsed_sec:.3f} "
            f"elapsed_ms={elapsed_ms} "
            f"folder_path={meta['folder_path']}"
        )
        return audiobook_id
    except Exception as err:
        print(f"[AudiobookScanner ERROR] Failed to save audiobook {folder_path}: {err}")
        try:
            # 로그에만 남으면 사용자가 모른다(예: 하위 폴더를 정리한 뒤 '트랙 파일 경로 중복'으로 등록 실패)
            from services.problem_service import ProblemService
            from services.scan_problem_service import _path_target_id
            norm = os.path.normpath(folder_path)
            ProblemService.report(CODE_SAVE_FAILED, 'book', _path_target_id(norm), db_type='audiobook',
                                  library_id=library_id, target_path=norm, title=os.path.basename(norm),
                                  detail=str(err)[:300])
        except Exception:
            pass
        return None


def _dispatch_audiobook_new_items_events(library_id, new_items):
    """새로 감지된 오디오북에 대해 표준 웹훅 이벤트(scan.new_books_detected) +
    플러그인 on_scan_new_books_detected 훅을 (일반 도서 스캔의
    tools/scanner/engine.py 패턴과 동일하게) 비동기로 디스패치한다.

    일반/성인 도서 스캔은 스캔 완료 시 이 두 가지를 이미 호출하지만, 오디오북 스캔
    경로(이 파일)는 별도 파이프라인이라 지금까지 아무 디스패치도 없었다 — 그래서
    webhook_new_books_notify 같은 플러그인이 오디오북 신간에는 반응하지 않았다.
    """
    if not new_items:
        return

    import threading

    def _worker():
        try:
            from repositories.category_repository import CategoryRepository
            lib_info = CategoryRepository.get_library_by_id('audiobook', library_id) if library_id else None
            library_name = (lib_info or {}).get('name') or f"Lib_{library_id}"

            sample = [it['title'] for it in new_items[:10]]
            event_payload = {
                'db_type': 'audiobook',
                'library_id': library_id,
                'library_name': library_name,
                'new_books_count': len(new_items),
                'sample_titles': sample,
            }

            try:
                from services.webhook_dispatcher import dispatch_webhook_event
                dispatch_webhook_event('scan.new_books_detected', event_payload)
            except Exception as e:
                print(f"[AudiobookScanner-Webhook] dispatch failed: {e}")

            try:
                from tools.scanner.engine import _dispatch_new_books_to_plugin_hooks
                _dispatch_new_books_to_plugin_hooks('audiobook', event_payload)
            except Exception as e:
                print(f"[AudiobookScanner-PluginHook] dispatch failed: {e}")
        except Exception as e:
            print(f"[AudiobookScanner-AsyncEvent ERROR] Failed to dispatch scan events: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def _keep_renamed_track_ids(repo, audiobook_id, folder_path, track_cache):
    """폴더 안에서 파일 이름만 바뀐 트랙을 찾아 경로를 고친다(트랙 id = 이어 듣기 위치 유지).
    사라진 트랙과 새 파일의 크기+수정시각(초)이 서로 하나씩만 맞을 때만 같은 파일로 본다. 이름 변경은
    로컬·GDrive 모두 수정시각을 유지한다. track_cache(경로 → 크기/시각/길이)도 새 경로로 옮겨 길이를 다시 재지 않는다."""
    rows = [r for r in repo.get_audiobook_tracks(audiobook_id) if r.get('file_path')]
    known = {os.path.normpath(str(r['file_path'])) for r in rows}
    gone = [r for r in rows if not os.path.exists(r['file_path'])]
    if not gone:
        return 0
    def key(size, mtime):
        return (int(size or 0), int(float(mtime or 0)))
    fresh = {}
    for root, _, files in os.walk(folder_path):
        for name in files:
            if not name.lower().endswith(AUDIO_EXTENSIONS):
                continue
            path = os.path.normpath(os.path.join(root, name))
            if path in known:
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            fresh.setdefault(key(st.st_size, st.st_mtime), []).append(path)
    gone_keys = {}
    for r in gone:
        gone_keys.setdefault(key(r.get('file_size'), r.get('file_mtime')), []).append(r)
    pairs = []
    for k, olds in gone_keys.items():
        news = fresh.get(k) or []
        if k[0] > 0 and k[1] > 0 and len(olds) == 1 and len(news) == 1:
            pairs.append((olds[0], news[0]))
    if not pairs:
        return 0
    repo.update_track_paths([(old['id'], new_path) for old, new_path in pairs])
    for old, new_path in pairs:
        old_path = os.path.normpath(str(old['file_path']))
        if old_path in track_cache:
            track_cache[new_path] = track_cache.pop(old_path)
        print(f"[AudiobookScanner][TRACK_RENAMED] audiobook_id={audiobook_id} track_id={old['id']} from={old_path} to={new_path}")
    return len(pairs)


def _audio_signature(folder_path, extensions=AUDIO_EXTENSIONS):
    """폴더 안 오디오(영상 스캐너는 영상) 파일의 {(상대 경로, 크기): 전체 경로}. 목록 정보만 써서 원격에서도 다운로드가 없다."""
    sig = {}
    base = os.path.normpath(folder_path)
    for root, _, files in os.walk(base):
        for name in files:
            if not name.lower().endswith(extensions):
                continue
            full = os.path.normpath(os.path.join(root, name))
            try:
                sig[(os.path.relpath(full, base), int(os.path.getsize(full)))] = full
            except OSError:
                continue
    return sig


def _audiobook_tracks(item_id):
    from repositories.audiobook_repository import AudiobookRepository
    return AudiobookRepository.get_audiobook_tracks(item_id)


class _MovedAudiobookFinder:
    """폴더 이름 변경/이동 인식: 새로 발견한 폴더의 트랙 구성(상대 경로+크기)이 '폴더가 사라진 기존 책'과
    같으면(기존 트랙이 모두 있으면) 그 책을 옮긴 것으로 본다. 새 폴더라는 실제 증거가 있을 때만 옮기므로
    마운트가 끊겨도 잘못 옮기지 않는다. 짝이 없는 사라진 책은 스캔 끝에 숨김(소프트 삭제) 후보가 된다.
    영상 스캐너도 같은 규칙을 쓴다(load_tracks=회차 조회, extensions=영상 확장자)."""

    def __init__(self, library_path, rows, load_tracks=None, extensions=AUDIO_EXTENSIONS):
        self.load_tracks = load_tracks or _audiobook_tracks
        self.extensions = extensions
        root = os.path.normpath(library_path)
        self.rows = [r for r in rows if not r.get('is_deleted') and
                     (os.path.normpath(r['folder_path']) == root or os.path.normpath(r['folder_path']).startswith(root + os.sep))]
        self._missing = None
        self.moved_ids = set()

    def missing(self):
        if self._missing is None:
            self._missing = [r for r in self.rows if not os.path.isdir(r['folder_path'])]
        return self._missing

    def find(self, new_folder):
        candidates = [r for r in self.missing() if r['id'] not in self.moved_ids]
        if not candidates:
            return None
        new_sig = _audio_signature(new_folder, self.extensions)
        matches = []
        for r in candidates:
            old_folder = os.path.normpath(r['folder_path'])
            tracks = self.load_tracks(r['id'])
            old_sig = {(os.path.relpath(os.path.normpath(t['file_path']), old_folder), int(t.get('file_size') or 0)): t['id']
                       for t in tracks if t.get('file_path')}
            if old_sig and set(old_sig) <= set(new_sig):
                matches.append((r, [(tid, new_sig[key]) for key, tid in old_sig.items()]))
        if len(matches) != 1:
            return None  # 없거나 애매하면 옮기지 않는다
        return matches[0]

    def unmatched_missing(self):
        return [r for r in self.missing() if r['id'] not in self.moved_ids]


def _hide_unmatched_missing(finder, library_path, library_id, db_type='audiobook', repo=None, log_prefix='AudiobookScanner'):
    """폴더가 사라졌고 옮겨진 곳도 없는 책(영상은 강좌)을 숨긴다. 카테고리 폴더에 접근할 수 없거나(마운트 끊김)
    한 번에 많이 사라지면(도서와 같은 대량 삭제 기준) 보류하고 로그만 남긴다."""
    if repo is None:
        from repositories.audiobook_repository import AudiobookRepository as repo
    missing = finder.unmatched_missing()
    if not missing:
        return 0
    try:
        reachable = os.path.isdir(library_path) and any(True for _ in os.scandir(library_path))
    except OSError:
        reachable = False
    if not reachable:
        print(f"[{log_prefix}][MISSING_HELD] library_id={library_id} reason=library_unreachable missing={len(missing)} library_path={library_path}")
        return 0
    from services.scan_problem_service import is_mass_missing
    if is_mass_missing(db_type, library_id, len(missing), len(finder.rows)):
        print(f"[{log_prefix}][MISSING_HELD] library_id={library_id} reason=mass_missing missing={len(missing)} total={len(finder.rows)} library_path={library_path}")
        return 0
    hidden = 0
    for r in missing:
        if repo.set_deleted(r['id'], True):
            hidden += 1
            print(f"[{log_prefix}][MISSING_HIDDEN] {db_type}_id={r['id']} folder_path={r['folder_path']}")
    return hidden


def scan_audiobook_library(library_path, library_id=None, force=False):
    """
    상위 오디오북 라이브러리 디렉토리를 순회하며 모든 오디오북 폴더를 스캔합니다.
    """
    if not os.path.exists(library_path):
        print(f"[AudiobookScanner Error] Library path does not exist: {library_path}")
        return 0

    count = 0
    skipped = 0
    errors = 0
    existing_folder_paths = set()
    skip_existing = not force
    library_started_at = time.perf_counter()
    new_items = []

    from repositories.audiobook_repository import AudiobookRepository
    from services.category_service import CategoryService
    folder_rows = AudiobookRepository.get_folder_rows(library_id)
    # 숨겨진(폴더가 사라졌던) 책은 '등록됨'으로 보지 않는다 - 폴더가 다시 나타나면 처리되며 복원된다
    existing_folder_paths = {os.path.normpath(str(r['folder_path'])) for r in folder_rows if not r.get('is_deleted')}
    moved_finder = _MovedAudiobookFinder(library_path, folder_rows)
    moved = 0
    changed = 0
    # 일반 스캔도 등록된 폴더의 파일 목록(상대 경로+크기)만 DB 트랙과 비교해, 달라진 폴더(파일 이름 변경·
    # 회차 추가/삭제)만 다시 처리한다. 목록 정보만 보므로 원격에서도 다운로드가 없다.
    track_signatures = AudiobookRepository.get_track_signatures(library_id) if skip_existing else {}
    music = CategoryService.is_music_library(library_id)

    print(
        "[AudiobookScanner][LIBRARY_SCAN_START] "
        f"library_id={library_id} "
        f"music={music} "
        f"force={force} "
        f"existing_records={len(existing_folder_paths)} "
        f"skip_policy={'default_skip_existing' if skip_existing else 'force_rescan_existing'} "
        f"library_path={library_path}"
    )

    # 라이브러리 디렉터리 내 하위 디렉터리들을 오디오북 단위로 탐색
    for root, dirs, files in os.walk(library_path):
        # audio.json 파일이 존재하거나 오디오 파일이 있는 최하위 디렉토리 감지
        has_audio_json = 'audio.json' in files
        has_audio_files = any(f.lower().endswith(AUDIO_EXTENSIONS) for f in files)
        # 음악: 곡 없이 CD1/Disc 2 같은 디스크 폴더만 있는 폴더가 앨범 하나 (디스크마다 따로 앨범이 되지 않게)
        is_multi_disc_album = music and not has_audio_files and any(is_disc_dir(d) for d in dirs)

        if has_audio_json or has_audio_files or is_multi_disc_album:
            if skip_existing and os.path.normpath(root) in existing_folder_paths and                     set(_audio_signature(root)) != track_signatures.get(os.path.normpath(root), set()):
                changed += 1
                print(f"[AudiobookScanner][CHANGED] library_id={library_id} reason=file_list_changed folder_path={os.path.normpath(root)}")
            elif skip_existing and os.path.normpath(root) in existing_folder_paths:
                skipped += 1
                print(
                    "[AudiobookScanner][SKIP_EXISTING] "
                    f"library_id={library_id} "
                    f"reason=already_exists_default_skip "
                    f"folder_path={os.path.normpath(root)}"
                )
                dirs.clear()
                continue
            was_new_folder = os.path.normpath(root) not in existing_folder_paths
            if was_new_folder:
                match = moved_finder.find(root)
                if match:
                    row, track_paths = match
                    AudiobookRepository.relocate_audiobook(row['id'], os.path.normpath(root), os.path.basename(os.path.normpath(root)), track_paths)
                    moved_finder.moved_ids.add(row['id'])
                    moved += 1
                    was_new_folder = False  # 새 책이 아니라 옮겨진 책 (신간 이벤트 없음)
                    print(f"[AudiobookScanner][MOVED] audiobook_id={row['id']} from={row['folder_path']} to={os.path.normpath(root)}")
            aid = scan_and_save_audiobook_folder(root, library_id=library_id, music=music)
            if aid:
                count += 1
                if was_new_folder:
                    try:
                        from repositories.audiobook_repository import AudiobookRepository as _AR
                        row = _AR.get_audiobook_by_id(aid)
                        title = (row or {}).get('title') or os.path.basename(root)
                    except Exception:
                        title = os.path.basename(root)
                    new_items.append({'id': aid, 'title': title})
                # 오디오북 단위를 감지했으므로 그 하위 디렉터리 깊이 탐색은 방지
                dirs.clear()
            else:
                errors += 1

    hidden = _hide_unmatched_missing(moved_finder, library_path, library_id)

    _dispatch_audiobook_new_items_events(library_id, new_items)

    library_elapsed_sec = time.perf_counter() - library_started_at
    library_elapsed_ms = int(library_elapsed_sec * 1000)

    print(
        "[AudiobookScanner][LIBRARY_SCAN_DONE] "
        f"library_id={library_id} "
        f"processed={count} "
        f"skipped={skipped} "
        f"errors={errors} "
        f"moved={moved} "
        f"changed={changed} "
        f"hidden={hidden} "
        f"force={force} "
        f"elapsed_sec={library_elapsed_sec:.3f} "
        f"elapsed_ms={library_elapsed_ms} "
        f"library_path={library_path}"
    )
    return count
