# -*- coding: utf-8 -*-
"""
audiobook_routes.py – 오디오북 전용 MP3 오디오 스트리밍 및 재생 진행도 API
"""
import os
import re
import sqlite3
from flask import Blueprint, request, Response, jsonify, session
from api.auth import login_required
import database

try:
    import requests
except Exception:
    requests = None

audiobook_bp = Blueprint('audiobook_api', __name__)

def _send_audio_range_response(file_path):
    """
    MP3 오디오 파일 Range Request (206 Partial Content) 스트리밍 서빙
    """
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Audio file not found'}), 404

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range', None)

    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
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

        length = byte2 - byte1 + 1

        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)

        rv = Response(data, 206, mimetype=mimetype, content_type=mimetype, direct_passthrough=True)
        rv.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        rv.headers.add('Content-Length', str(length))
        return rv
    else:
        with open(file_path, 'rb') as f:
            data = f.read(1024 * 1024 * 4) # 첫 4MB 조각 서빙
        rv = Response(data, 200, mimetype=mimetype, content_type=mimetype, direct_passthrough=True)
        rv.headers.add('Accept-Ranges', 'bytes')
        rv.headers.add('Content-Length', str(file_size))
        return rv

@audiobook_bp.route('/api/media/audiobooks/<int:aid>/cover', methods=['GET'])
def get_audiobook_cover(aid):
    """오디오북 대표 앨범 포스터 이미지 서빙"""
    conn = database.get_connection('audiobook')
    cursor = conn.cursor()
    cursor.execute("SELECT poster, title FROM audiobooks WHERE id = ?", (aid,))
    row = cursor.fetchone()
    conn.close()

    if row and row['poster']:
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
    title = row['title'] if row else 'Audiobook'
    from api.stream import _build_fallback_svg
    svg_data = _build_fallback_svg(title, file_format='audiobook', seed=str(aid))
    return Response(svg_data, mimetype='image/svg+xml')

@audiobook_bp.route('/api/media/audiobooks/<int:aid>/tracks/<int:tid>/stream', methods=['GET'])
@login_required
def stream_audiobook_track(aid, tid):
    """오디오북 특정 트랙 MP3 오디오 스트리밍"""
    conn = database.get_connection('audiobook')
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM audiobook_tracks WHERE id = ? AND audiobook_id = ?", (tid, aid))
    row = cursor.fetchone()
    conn.close()

    if not row or not row['file_path']:
        return jsonify({'success': False, 'error': 'Track not found'}), 404

    return _send_audio_range_response(row['file_path'])

@audiobook_bp.route('/api/media/audiobooks/<int:aid>/progress', methods=['GET', 'POST'])
@login_required
def audiobook_progress_api(aid):
    user_id = session.get('user_id', 1)
    conn = database.get_connection('audiobook')
    cursor = conn.cursor()

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

        # 총 진행율 계산
        total_pct = 0.0
        try:
            cursor.execute("SELECT total_duration FROM audiobooks WHERE id = ?", (aid,))
            ab_row = cursor.fetchone()
            if ab_row and ab_row['total_duration'] > 0:
                total_pct = min(100.0, (current_time / ab_row['total_duration']) * 100.0)
        except Exception:
            pass

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO audiobook_progress (
                    audiobook_id, user_id, current_track_id, current_time, total_progress_pct, playback_rate, is_completed, last_listened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (aid, user_id, track_id, current_time, total_pct, playback_rate, is_completed))
            conn.commit()

            # 최근 읽은 도서 캐시를 즉시 무효화하여 대시보드 반영 지연(최대 1시간)을 방지
            try:
                from utils.redis_helper import redis_delete_pattern
                redis_delete_pattern(f"cache:history*:{'audiobook'}:{user_id}")
            except Exception:
                pass

            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            conn.close()
    else:
        cursor.execute("SELECT * FROM audiobook_progress WHERE audiobook_id = ? AND user_id = ?", (aid, user_id))
        row = cursor.fetchone()
        conn.close()
        return jsonify({'success': True, 'progress': dict(row) if row else None})
