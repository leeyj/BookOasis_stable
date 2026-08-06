# -*- coding: utf-8 -*-
"""
audiobook_routes.py – 오디오북 전용 MP3 오디오 스트리밍 및 재생 진행도 API
"""
import os
import re
import sqlite3
import subprocess
import shutil
from flask import Blueprint, request, Response, jsonify, session
from api.auth import login_required, check_adult_permission
import database

try:
    import requests
except Exception:
    requests = None

audiobook_bp = Blueprint('audiobook_api', __name__)

UNSUPPORTED_BROWSER_AUDIO_EXTS = {'wma', 'ape', 'dts', 'ac3', 'ra', 'ram', 'au', 'voc', 'wv'}

def _stream_transcoded_audio(file_path):
    """FFmpeg를 이용하여 브라우저 미지원 오디오 포맷을 audio/mpeg (MP3) 스트림으로 온더플라이 변환 서빙"""
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        return None

    cmd = [
        ffmpeg_path,
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
        200,
        mimetype='audio/mpeg',
        content_type='audio/mpeg',
        direct_passthrough=True
    )
    rv.headers.add('Cache-Control', 'no-cache, no-transform')
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

def _send_audio_range_response(file_path):
    """
    MP3 오디오 파일 Range Request (206 Partial Content) 스트리밍 서빙
    """
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Audio file not found'}), 404

    ext = os.path.splitext(file_path)[1].lstrip('.').lower()

    # 브라우저 미지원 포맷일 경우 FFmpeg 온더플라이 트랜스코딩 수행
    if ext in UNSUPPORTED_BROWSER_AUDIO_EXTS:
        transcoded = _stream_transcoded_audio(file_path)
        if transcoded:
            print(f"[Audio-Transcode] On-the-fly MP3 transcoding served for {ext}: {file_path}")
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
        poster_path = row['poster']
        if poster_path.startswith(('http://', 'https://')):
            if requests is not None:
                try:
                    remote_res = requests.get(poster_path, timeout=5)
                    if remote_res.ok and remote_res.content:
                        remote_type = remote_res.headers.get('Content-Type', '').split(';')[0].strip() or 'image/jpeg'
                        return Response(remote_res.content, mimetype=remote_type)
                except Exception:
                    pass
        if os.path.exists(poster_path):
            ext = os.path.splitext(poster_path)[1].lstrip('.').lower()
            mimetype = 'image/jpeg' if ext in ('jpg', 'jpeg') else f'image/{ext}'
            from flask import send_file
            return send_file(poster_path, mimetype=mimetype)

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
        total_pct = 0.0
        try:
            ab_row = AudiobookRepository.get_audiobook_by_id(aid)
            if ab_row and ab_row.get('total_duration') and ab_row['total_duration'] > 0:
                total_pct = min(100.0, (current_time / ab_row['total_duration']) * 100.0)
        except Exception:
            pass

        try:
            AudiobookRepository.save_audiobook_progress(aid, user_id, track_id, current_time, total_pct, playback_rate, is_completed)

            # 최근 읽은 도서 캐시를 즉시 무효화하여 대시보드 반영 지연(최대 1시간)을 방지
            try:
                from utils.redis_helper import redis_delete_pattern
                redis_delete_pattern(f"cache:history*:{'audiobook'}:{user_id}")
            except Exception:
                pass

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        progress_row = AudiobookRepository.get_audiobook_progress(aid, user_id)
        return jsonify({'success': True, 'progress': progress_row})
