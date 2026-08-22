# -*- coding: utf-8 -*-
"""
audiobook_routes.py – 오디오북 전용 MP3 오디오 스트리밍 및 재생 진행도 API
"""
import os
import re
import sqlite3
import subprocess
import shutil
import json
from flask import Blueprint, request, Response, jsonify, session
from api.auth import login_required, check_adult_permission
import database

audiobook_bp = Blueprint('audiobook_api', __name__)

UNSUPPORTED_BROWSER_AUDIO_EXTS = {'wma', 'ape', 'dts', 'ac3', 'ra', 'ram', 'au', 'voc', 'wv'}

# 브라우저가 네이티브로 재생 가능한 오디오 코덱. 확장자만 보고 판단하면 강좌/변환 도구가
# 실제로는 다른 코덱(wma, alac 등)을 .mp3/.m4a 확장자로 잘못 저장한 파일을 "호환"으로
# 오판해 NotSupportedError가 난다 (video의 컨테이너 오판 버그와 동일한 원인).
BROWSER_COMPATIBLE_AUDIO_CODECS = {
    'mp3', 'aac', 'vorbis', 'opus', 'flac', 'pcm_s16le', 'pcm_u8', 'pcm_s24le'
}

# 확장자가 주장하는 컨테이너와 ffprobe가 실측한 실제 컨테이너(format_name)가 일치하는지
# 검증하기 위한 힌트. video_scanner.py::CONTAINER_FORMAT_NAME_HINTS와 동일한 목적/패턴 —
# 실사용 사례(2026-08-22)로 확인: 오디오북 강좌 다운로드 도구가 실제로는 MPEG-TS 스트림인
# 파일을 확장자만 `.mp3`로 잘못 저장했다(ffprobe format_name='mpegts', 코덱 자체는 정상
# mp3). 코덱만 보는 판정으로는 "호환"으로 오판해 HTML5 <audio> 네이티브 재생이
# NotSupportedError로 실패했다 — 비디오 쪽과 원인이 같으므로 판정 로직도 같은 패턴으로
# 맞춰서, 나중에 두 스트리밍 경로를 함께 디버깅할 때 헷갈리지 않게 한다.
AUDIO_CONTAINER_FORMAT_NAME_HINTS = {
    'mp3': ('mp3',),
    'm4a': ('mp4', 'm4a'),
    'm4b': ('mp4', 'm4a'),
    'flac': ('flac',),
    'aac': ('aac', 'loas', 'adts'),
    'ogg': ('ogg',),
    'wav': ('wav',),
    'opus': ('ogg',),
}

# 실제 코덱 probe 결과 캐시 (경로+mtime+size로 키 구성, 서버 프로세스 생존 중에만 유효).
# 원격(rclone/GDrive) 마운트에서 매 Range 요청마다 ffprobe를 재실행하면 지연이 커지므로
# 파일이 바뀌지 않는 한 최초 1회만 probe한다.
_AUDIO_PROBE_CACHE = {}


def _probe_audio_info(file_path):
    """ffprobe로 오디오 스트림의 실제 codec_name, 실제 컨테이너 포맷명(format_name),
    duration(초)을 한 번에 조회. (codec_name, format_name, duration) 튜플 반환,
    실패 시 ('', '', 0.0). video_scanner.py::_probe_video_info와 동일한 JSON 단일 호출
    패턴.

    duration은 트랜스코딩 스트림에서 Range(시킹) 요청을 처리할 때, 요청된 byte offset을
    ffmpeg -ss 초 단위 오프셋으로 환산하기 위해 필요하다."""
    try:
        stat = os.stat(file_path)
    except OSError:
        return '', '', 0.0

    cache_key = file_path
    cached = _AUDIO_PROBE_CACHE.get(cache_key)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2], cached[3], cached[4]

    codec_name = ''
    format_name = ''
    duration = 0.0
    ffprobe_path = shutil.which('ffprobe')
    if ffprobe_path:
        try:
            cmd = [
                ffprobe_path,
                '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name',
                '-show_entries', 'format=duration,format_name',
                '-of', 'json',
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
            if completed.returncode == 0:
                data = json.loads(completed.stdout or '{}')
                fmt = data.get('format') or {}
                format_name = str(fmt.get('format_name') or '').lower()
                try:
                    duration = float(fmt.get('duration') or 0.0)
                except (TypeError, ValueError):
                    duration = 0.0
                streams = data.get('streams') or []
                if streams:
                    codec_name = str(streams[0].get('codec_name') or '').lower()
        except Exception as err:
            print(f"[Audio-Probe] ffprobe error for {file_path}: {err}")

    _AUDIO_PROBE_CACHE[cache_key] = (stat.st_mtime_ns, stat.st_size, codec_name, format_name, duration)
    return codec_name, format_name, duration

# 트랜스코딩 출력의 고정 비트레이트 (아래 -ab 값과 반드시 일치시켜야 seek 시 byte->시간
# 환산이 정확함). 192kbps = 192000 bit/s / 8 = 24000 byte/s.
TRANSCODE_BYTES_PER_SEC = 192000 // 8


def _stream_transcoded_audio(file_path, start_time=0.0):
    """FFmpeg를 이용하여 브라우저 미지원/손상 오디오 포맷을 audio/mpeg (MP3) 스트림으로
    온더플라이 변환 서빙. start_time(초)이 주어지면 그 지점부터 트랜스코딩해 Range(시킹)
    요청을 지원한다."""
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        return None

    cmd = [ffmpeg_path]
    if start_time > 0:
        # -i 앞에 두어 입력 단에서 빠르게 탐색(fast seek)한다.
        cmd += ['-ss', f'{start_time:.3f}']
    cmd += [
        '-i', file_path,
        '-vn',
        '-f', 'mp3',
        '-acodec', 'libmp3lame',
        '-ab', '192k',
        '-ar', '44100',
        'pipe:1'
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception as err:
        print(f"[Audio-Transcode] FFmpeg spawn error: {err}")
        return None

    def generate():
        try:
            while True:
                chunk = proc.stdout.read(1024 * 64)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                proc.terminate()
            except Exception:
                pass

    rv = Response(
        generate(),
        206 if start_time > 0 else 200,
        mimetype='audio/mpeg',
        content_type='audio/mpeg',
        direct_passthrough=True
    )
    rv.headers.add('Cache-Control', 'no-cache, no-transform')
    rv.headers.add('Accept-Ranges', 'bytes')
    return rv


def _iter_file_chunks(file_path, start=0, length=None, chunk_size=1024 * 256):
    """Yield file content in chunks to avoid loading large audio files into memory."""
    remaining = length
    with open(file_path, 'rb') as f:
        if start > 0:
            f.seek(start)

        while True:
            if remaining is None:
                data = f.read(chunk_size)
            else:
                if remaining <= 0:
                    break
                data = f.read(min(chunk_size, remaining))

            if not data:
                break

            yield data
            if remaining is not None:
                remaining -= len(data)

def _needs_audio_transcode(file_path, ext):
    """이 파일을 브라우저에 그대로 서빙 가능한지 판정. (needs_transcode, probed_duration)
    반환 — probed_duration은 트랜스코딩이 필요한 경우 seek 시간 환산에, 아닌 경우 호출부가
    참고용으로만 쓴다(필요 없으면 0.0). 스트리밍 응답 생성과 "재생 전 미리 트랜스코딩
    여부만 알고 싶은" 가벼운 상태 조회 엔드포인트 양쪽에서 공유한다."""
    needs_transcode = ext in UNSUPPORTED_BROWSER_AUDIO_EXTS
    probed_duration = 0.0
    if not needs_transcode:
        # 확장자는 정상(mp3 등)으로 보여도 실제 코덱/컨테이너가 다를 수 있음
        # (예: wma를 mp3로 잘못 저장했거나, 강좌 다운로드 도구가 실제로는 MPEG-TS
        # 스트림인 파일을 확장자만 mp3로 잘못 저장한 경우 — video의 container_format_name
        # 오판 버그와 동일한 원인). 실제 코덱+컨테이너를 probe해 비호환이면 트랜스코딩한다.
        actual_codec, actual_format_name, probed_duration = _probe_audio_info(file_path)
        format_hints = AUDIO_CONTAINER_FORMAT_NAME_HINTS.get(ext)
        if actual_codec and actual_codec not in BROWSER_COMPATIBLE_AUDIO_CODECS:
            print(f"[Audio-Probe] Mismatched codec for .{ext}: actual codec is '{actual_codec}', forcing transcode ({file_path})")
            needs_transcode = True
        elif format_hints and actual_format_name and not any(hint in actual_format_name for hint in format_hints):
            print(f"[Audio-Probe] Mismatched container for .{ext}: actual format_name is '{actual_format_name}', forcing transcode ({file_path})")
            needs_transcode = True
    return needs_transcode, probed_duration


def _send_audio_range_response(file_path):
    """
    MP3 오디오 파일 Range Request (206 Partial Content) 스트리밍 서빙
    """
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Audio file not found'}), 404

    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    needs_transcode, probed_duration = _needs_audio_transcode(file_path, ext)

    if needs_transcode:
        # 트랜스코딩 출력은 고정 비트레이트(TRANSCODE_BYTES_PER_SEC)이므로, 요청받은 byte
        # offset을 시간으로 환산해 ffmpeg -ss로 그 지점부터 다시 인코딩하면 시킹이 된다.
        if not probed_duration:
            _, _, probed_duration = _probe_audio_info(file_path)

        start_time = 0.0
        content_range_header = None
        range_header = request.headers.get('Range', None)
        if range_header and probed_duration > 0:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match and match.group(1):
                byte1 = int(match.group(1))
                total_size = max(int(probed_duration * TRANSCODE_BYTES_PER_SEC), byte1 + 1)
                if byte1 > 0:
                    start_time = byte1 / TRANSCODE_BYTES_PER_SEC
                    content_range_header = f'bytes {byte1}-{total_size - 1}/{total_size}'

        transcoded = _stream_transcoded_audio(file_path, start_time=start_time)
        if transcoded:
            if content_range_header:
                transcoded.headers.set('Content-Range', content_range_header)
            print(f"[Audio-Transcode] On-the-fly MP3 transcoding served for {ext} (start={start_time:.1f}s): {file_path}")
            return transcoded

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range', None)

    mimetype_map = {
        'mp3': 'audio/mpeg',
        'm4a': 'audio/mp4',
        'm4b': 'audio/mp4',
        'flac': 'audio/flac',
        'aac': 'audio/aac',
        'ogg': 'audio/ogg',
        'wav': 'audio/wav',
        'opus': 'audio/opus'
    }
    mimetype = mimetype_map.get(ext, 'audio/mpeg')

    if range_header:
        byte1, byte2 = 0, None
        match = re.search(r'bytes=(\d+)-(\d+)?', range_header)
        if match:
            groups = match.groups()
            if groups[0]:
                byte1 = int(groups[0])
            if groups[1]:
                byte2 = int(groups[1])

        if byte2 is None or byte2 >= file_size:
            byte2 = file_size - 1

        if byte1 >= file_size:
            rv = Response(status=416)
            rv.headers.add('Content-Range', f'bytes */{file_size}')
            rv.headers.add('Accept-Ranges', 'bytes')
            rv.headers.add('Cache-Control', 'no-transform')
            return rv

        length = byte2 - byte1 + 1

        rv = Response(
            _iter_file_chunks(file_path, start=byte1, length=length),
            206,
            mimetype=mimetype,
            content_type=mimetype,
            direct_passthrough=True
        )
        rv.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        rv.headers.add('Content-Length', str(length))
        rv.headers.add('Cache-Control', 'no-transform')
        return rv

    else:
        rv = Response(
            _iter_file_chunks(file_path),
            200,
            mimetype=mimetype,
            content_type=mimetype,
            direct_passthrough=True
        )
        rv.headers.add('Accept-Ranges', 'bytes')
        rv.headers.add('Content-Length', str(file_size))
        rv.headers.add('Cache-Control', 'no-transform')
        return rv


def _has_audiobook_library_access(aid):
    user_id = session.get('user_id')
    role = session.get('role')
    if role == 'admin':
        return True
    if not user_id:
        return False

    from repositories.audiobook_repository import AudiobookRepository
    from repositories.category_repository import CategoryRepository
    ab = AudiobookRepository.get_audiobook_by_id(aid)
    if not ab or not ab.get('library_id'):
        return False
    return CategoryRepository.check_user_category_access('audiobook', user_id, ab['library_id'])

@audiobook_bp.route('/api/media/audiobooks/<int:aid>/cover', methods=['GET'])
def get_audiobook_cover(aid):
    """오디오북 대표 앨범 포스터 이미지 서빙"""
    if not _has_audiobook_library_access(aid):
        return jsonify({'success': False, 'error': '오디오북 접근 권한이 없습니다.'}), 403

    from repositories.audiobook_repository import AudiobookRepository
    row = AudiobookRepository.get_audiobook_by_id(aid)

    if row and row.get('poster'):
        from utils.cover_helper import get_or_cache_remote_poster_webp
        cache_path = get_or_cache_remote_poster_webp(row['poster'], 'audio', library_id=row.get('library_id'))
        if cache_path:
            from api.stream import send_cached_cover_file
            return send_cached_cover_file(cache_path)

    # Fallback SVG 생성
    title = row.get('title') if row else 'Audiobook'
    from api.stream import _build_fallback_svg
    svg_data = _build_fallback_svg(title, file_format='audiobook', seed=str(aid))
    return Response(svg_data, mimetype='image/svg+xml')

@audiobook_bp.route('/api/media/audiobooks/<int:aid>/tracks/<int:tid>/stream', methods=['GET'])
@login_required
def stream_audiobook_track(aid, tid):
    """오디오북 특정 트랙 MP3 오디오 스트리밍"""
    if not _has_audiobook_library_access(aid):
        return jsonify({'success': False, 'error': '오디오북 접근 권한이 없습니다.'}), 403

    from repositories.audiobook_repository import AudiobookRepository
    row = AudiobookRepository.get_track_by_id_and_audiobook_id(tid, aid)

    if not row or not row.get('file_path'):
        return jsonify({'success': False, 'error': 'Track not found'}), 404

    return _send_audio_range_response(row['file_path'])

@audiobook_bp.route('/api/media/audiobooks/<int:aid>/tracks/<int:tid>/transcode-status', methods=['GET'])
@login_required
def audiobook_track_transcode_status(aid, tid):
    """이 트랙이 실제로 트랜스코딩을 거쳐 서빙되는지 가볍게 조회 (ffmpeg 프로세스는
    띄우지 않고 ffprobe 판정만 재사용 — mtime/size 캐시라 반복 호출도 빠름). 플레이어가
    재생 시작 시 이 값을 확인해 "트랜스코딩 중" 경고 배너를 보여줄지 결정한다."""
    if not _has_audiobook_library_access(aid):
        return jsonify({'success': False, 'error': '오디오북 접근 권한이 없습니다.'}), 403

    from repositories.audiobook_repository import AudiobookRepository
    row = AudiobookRepository.get_track_by_id_and_audiobook_id(tid, aid)
    if not row or not row.get('file_path'):
        return jsonify({'success': False, 'error': 'Track not found'}), 404

    file_path = row['file_path']
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Audio file not found'}), 404

    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    needs_transcode, _ = _needs_audio_transcode(file_path, ext)
    return jsonify({'success': True, 'needs_transcode': needs_transcode})

@audiobook_bp.route('/api/media/audiobooks/<int:aid>/progress', methods=['GET', 'POST'])
@login_required
def audiobook_progress_api(aid):
    if not _has_audiobook_library_access(aid):
        return jsonify({'success': False, 'error': '오디오북 접근 권한이 없습니다.'}), 403

    user_id = session.get('user_id', 1)
    from repositories.audiobook_repository import AudiobookRepository

    if request.method == 'POST':
        data = request.get_json(force=True, silent=True)
        if not data and request.data:
            try:
                import json as _json
                data = _json.loads(request.data.decode('utf-8'))
            except Exception:
                data = {}
        data = data or {}
        track_id = data.get('current_track_id')
        current_time = float(data.get('current_time', 0.0))
        playback_rate = float(data.get('playback_rate', 1.0))
        is_completed = 1 if data.get('is_completed') else 0
        track_row = None

        # 현재 오디오북에 속하지 않는 track_id가 저장되지 않도록 방어한다.
        if track_id is not None:
            try:
                track_id_int = int(track_id)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': 'Invalid current_track_id'}), 400

            track_row = AudiobookRepository.get_track_by_id_and_audiobook_id(track_id_int, aid)
            if not track_row:
                return jsonify({'success': False, 'error': 'Track does not belong to audiobook'}), 400
            track_id = track_id_int

        # 총 진행율 계산
        total_pct = 100.0 if is_completed else 0.0
        if not is_completed:
            try:
                ab_row = AudiobookRepository.get_audiobook_by_id(aid)
                if ab_row and ab_row.get('total_duration') and ab_row['total_duration'] > 0:
                    total_pct = min(100.0, (current_time / ab_row['total_duration']) * 100.0)
            except Exception:
                pass

        try:
            AudiobookRepository.save_audiobook_progress(aid, user_id, track_id, current_time, total_pct, playback_rate, is_completed)
            track_progress_pct = 0.0
            track_is_completed = 0
            completed_track_count = 0
            if track_id is not None and track_row:
                track_duration = float(track_row.get('duration') or 0.0)
                if track_duration > 0:
                    track_progress_pct = min(100.0, max(0.0, (current_time / track_duration) * 100.0))
                    track_is_completed = 1 if track_progress_pct >= 95.0 else 0
                AudiobookRepository.save_audiobook_track_progress(
                    aid,
                    user_id,
                    track_id,
                    current_time,
                    track_progress_pct,
                    track_is_completed,
                )

            if is_completed:
                try:
                    tracks = AudiobookRepository.get_audiobook_tracks(aid)
                    completed_track_count = AudiobookRepository.mark_audiobook_tracks_completed(aid, int(user_id), tracks)
                    track_progress_pct = 100.0
                    track_is_completed = 1
                except Exception:
                    completed_track_count = 0

            # 최근 읽은 도서 캐시를 즉시 무효화하여 대시보드 반영 지연(최대 1시간)을 방지
            try:
                from utils.redis_helper import redis_delete_pattern
                redis_delete_pattern(f"cache:history*:{'audiobook'}:{user_id}:*")
            except Exception:
                pass
            if is_completed:
                try:
                    from services.series_service import SeriesService
                    SeriesService.invalidate_all_books_cache()
                except Exception:
                    pass

            return jsonify({
                'success': True,
                'track_id': track_id,
                'track_progress_pct': track_progress_pct,
                'track_is_completed': track_is_completed,
                'completed_track_count': completed_track_count,
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        progress_row = AudiobookRepository.get_audiobook_progress(aid, user_id)
        return jsonify({'success': True, 'progress': progress_row})
