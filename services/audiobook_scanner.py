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


def parse_audiobook_folder(folder_path, existing_track_cache=None, remote_fast_path=False):
    """
    단일 오디오북 디렉터리를 분석하여 메타데이터 및 트랙 목록을 파싱합니다.
    """
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return None

    folder_name = os.path.basename(os.path.normpath(folder_path))
    audio_files = []

    # 오디오 파일 검색
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(AUDIO_EXTENSIONS):
                full_path = os.path.normpath(os.path.join(root, file))
                audio_files.append(full_path)

    if not audio_files:
        return None

    # 트랙 파일 자연어 순서 정렬
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

    if os.path.exists(metadata_json_path):
        try:
            with open(metadata_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                meta['title'] = str(data.get('title', '')).strip()
                meta['publisher'] = str(data.get('publisher', '')).strip()
                meta['description'] = str(data.get('description', '')).strip()
                meta['premiered'] = str(data.get('publishedDate', '') or data.get('publishedYear', '')).strip()
                meta['isbn'] = str(data.get('isbn', '')).strip()
                meta['web_id'] = str(data.get('web_id', '')).strip()

                authors_list = data.get('authors', [])
                narrators_list = data.get('narrators', [])
                author_str = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list or '')
                if narrators_list and isinstance(narrators_list, list):
                    narrator_str = ", ".join(narrators_list[:3])
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
    elif os.path.exists(audio_json_path):
        try:
            with open(audio_json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
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

    # audio.json / metadata.json에 title/author가 누락되었거나 없으면 폴더명 fallback ("저자 - 제목")
    if not meta['title'] or not meta['author']:
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
        if (
            cache_row and
            int(cache_row.get('file_size', -1)) == int(file_size) and
            int(float(cache_row.get('file_mtime', -1.0) or -1.0)) == int(file_mtime)
        ):
            duration = float(cache_row.get('duration', 0.0) or 0.0)
            duration_cache_hits += 1
            duration_source = 'cache'
        else:
            if use_metadata_track_durations:
                duration = float(metadata_track_durations[idx - 1] or 0.0)
                metadata_duration_hits += 1
                duration_source = 'metadata'
            else:
                duration, file_size = get_audio_duration_and_size(
                    fpath,
                    file_size=file_size,
                    remote_fast_path=remote_fast_path
                )
                metadata_duration_fallbacks += 1
                file_probe_hits += 1

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

        code_match = re.search(r'(\d+[A-Za-z]|\d+)', fname)
        track_code = code_match.group(1) if code_match else str(idx)

        ext = os.path.splitext(fname)[1].lstrip('.').lower()

        tracks.append({
            'track_number': idx,
            'track_code': track_code,
            'filename': display_fname,
            'file_path': fpath,
            'file_mtime': file_mtime,
            'file_size': file_size,
            'duration': duration,
            'format': ext
        })

    meta['total_duration'] = total_duration
    meta['total_tracks'] = len(tracks)

    return {
        'meta': meta,
        'tracks': tracks,
        'duration_cache_hits': duration_cache_hits,
        'metadata_duration_hits': metadata_duration_hits,
        'metadata_duration_fallbacks': metadata_duration_fallbacks,
        'metadata_track_duration_mode': use_metadata_track_durations,
        'file_probe_hits': file_probe_hits
    }


def scan_and_save_audiobook_folder(folder_path, library_id=None):
    """
    단일 오디오북 폴더를 스캔하여 오디오북 DB에 저장/업데이트합니다.
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
                    'duration': float(r.get('duration') or 0.0)
                }

        parse_started_at = time.perf_counter()
        result = parse_audiobook_folder(
            folder_path,
            existing_track_cache=existing_track_cache,
            remote_fast_path=remote_fast_path
        )
        parse_elapsed_sec = time.perf_counter() - parse_started_at
        if not result:
            return None

        meta = result['meta']
        tracks = result['tracks']
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
        return None


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

    from repositories.audiobook_repository import AudiobookRepository
    raw_paths = AudiobookRepository.get_folder_paths(library_id)
    existing_folder_paths = {os.path.normpath(str(p)) for p in raw_paths if p}

    print(
        "[AudiobookScanner][LIBRARY_SCAN_START] "
        f"library_id={library_id} "
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

        if has_audio_json or has_audio_files:
            if skip_existing and os.path.normpath(root) in existing_folder_paths:
                skipped += 1
                print(
                    "[AudiobookScanner][SKIP_EXISTING] "
                    f"library_id={library_id} "
                    f"reason=already_exists_default_skip "
                    f"folder_path={os.path.normpath(root)}"
                )
                dirs.clear()
                continue
            aid = scan_and_save_audiobook_folder(root, library_id=library_id)
            if aid:
                count += 1
                # 오디오북 단위를 감지했으므로 그 하위 디렉터리 깊이 탐색은 방지
                dirs.clear()
            else:
                errors += 1

    library_elapsed_sec = time.perf_counter() - library_started_at
    library_elapsed_ms = int(library_elapsed_sec * 1000)

    print(
        "[AudiobookScanner][LIBRARY_SCAN_DONE] "
        f"library_id={library_id} "
        f"processed={count} "
        f"skipped={skipped} "
        f"errors={errors} "
        f"force={force} "
        f"elapsed_sec={library_elapsed_sec:.3f} "
        f"elapsed_ms={library_elapsed_ms} "
        f"library_path={library_path}"
    )
    return count
