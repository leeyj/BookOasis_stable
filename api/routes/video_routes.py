# -*- coding: utf-8 -*-
"""
video_routes.py – 영상 강좌 목록/커버/스트리밍/재생 진행도 API
"""
import os
import re
import shlex
import subprocess
import threading
from flask import Blueprint, request, Response, jsonify, session
from api.auth import login_required, admin_required
import database

try:
    import requests
except Exception:
    requests = None

video_bp = Blueprint('video_api', __name__)

VIDEO_MIMETYPE_MAP = {
    'mkv': 'video/x-matroska',
    'mp4': 'video/mp4',
    'm4v': 'video/mp4',
    'mov': 'video/quicktime',
    'webm': 'video/webm',
    'avi': 'video/x-msvideo',
    'ts': 'video/mp2t',
}


def _iter_file_chunks(file_path, start=0, length=None, chunk_size=1024 * 256):
    """Yield file content in chunks to avoid loading large video files into memory."""
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


def _send_video_range_response(file_path):
    """
    영상 파일 Range Request (206 Partial Content) 스트리밍 서빙
    """
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Video file not found'}), 404

    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    mimetype = VIDEO_MIMETYPE_MAP.get(ext, 'video/mp4')

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range', None)

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


def _log_ffmpeg_stderr(proc, video_id, episode_id):
    """트랜스코딩 ffmpeg 프로세스의 stderr를 서버 로그로 흘려보낸다 (파라미터 오류 진단용)."""
    try:
        for line in iter(proc.stderr.readline, b''):
            if not line:
                break
            print(f"[Video-Transcode][vid={video_id} ep={episode_id}] {line.decode('utf-8', errors='replace').rstrip()}")
    except Exception:
        pass


DEFAULT_CPU_TRANSCODE_ARGS = '-c:v libx264 -preset veryfast -crf 23 -c:a aac -b:a 128k'
DEFAULT_VAAPI_TRANSCODE_ARGS = '-vf format=nv12,hwupload -c:v h264_vaapi -qp 24 -c:a aac -b:a 128k'

# 프로세스 생애주기 동안 VAAPI 가용 여부를 device_path 별로 캐싱한다. 요청마다
# ffmpeg -h encoder=... 를 새로 실행하는 건 낭비이고, 하드웨어 상태는 컨테이너 재시작
# 전까지 바뀌지 않으므로 최초 1회(또는 관리자가 "지금 점검"을 눌렀을 때) 갱신하면 충분하다.
_vaapi_availability_cache = {}


def _detect_vaapi_available(device_path):
    if device_path in _vaapi_availability_cache:
        return _vaapi_availability_cache[device_path]

    available = False
    if os.path.exists(device_path):
        rc, out = _run_cmd(['ffmpeg', '-hide_banner', '-h', 'encoder=h264_vaapi'])
        available = bool(rc == 0 and 'Unknown encoder' not in out and 'h264_vaapi' in out)

    _vaapi_availability_cache[device_path] = available
    return available


def _stream_transcoded_video(file_path, video_id=None, episode_id=None):
    """
    브라우저가 원본을 직접 재생할 수 없는 경우(needs_transcode=1)의 폴백 경로.
    정책: 1) 브라우저 직접 재생 우선(이 함수 호출 이전 단계에서 이미 걸러짐)
          2) 안 되면 ffmpeg로 트랜스코딩
          3) ffmpeg는 CPU(libx264) 기본, VAAPI 하드웨어 가속이 감지되면 그것을 사용
    각 모드의 기본 인코딩 옵션은 설정 화면(FFMPEG_TRANSCODE_ARGS/FFMPEG_VAAPI_ARGS)에서
    재정의할 수 있다. 원본 그대로의 Range 서빙과 달리 HTTP Range를 지원하지 않으므로
    (항상 처음부터 파이프 출력), 브라우저에서 임의 위치 탐색(seek) 시 처음부터 다시
    트랜스코딩되어 원본 직접 스트리밍보다 반응이 느릴 수 있다.
    """
    from services.settings_service import SettingsService
    device_path = SettingsService.get('FFMPEG_VAAPI_DEVICE', '/dev/dri/renderD128') or '/dev/dri/renderD128'
    use_vaapi = _detect_vaapi_available(device_path)

    default_args = DEFAULT_VAAPI_TRANSCODE_ARGS if use_vaapi else DEFAULT_CPU_TRANSCODE_ARGS
    setting_key = 'FFMPEG_VAAPI_ARGS' if use_vaapi else 'FFMPEG_TRANSCODE_ARGS'
    args_str = SettingsService.get(setting_key, '') or default_args

    try:
        extra_args = shlex.split(args_str)
    except ValueError as e:
        return jsonify({'success': False, 'error': f'{setting_key} 파싱 실패: {e}'}), 500

    pre_input_args = ['-vaapi_device', device_path] if use_vaapi else []

    cmd = (
        ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'warning']
        + pre_input_args
        + ['-i', file_path]
        + extra_args
        + ['-movflags', 'frag_keyframe+empty_moov+default_base_moof', '-f', 'mp4', 'pipe:1']
    )

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'ffmpeg 실행 파일을 찾을 수 없습니다.'}), 500

    print(f"[Video-Transcode][vid={video_id} ep={episode_id}] mode={'vaapi' if use_vaapi else 'cpu'} cmd={' '.join(cmd)}")
    threading.Thread(target=_log_ffmpeg_stderr, args=(proc, video_id, episode_id), daemon=True).start()

    def generate():
        try:
            while True:
                chunk = proc.stdout.read(1024 * 256)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            if proc.poll() is None:
                proc.terminate()

    rv = Response(generate(), 200, mimetype='video/mp4', content_type='video/mp4', direct_passthrough=True)
    rv.headers.add('Cache-Control', 'no-store')
    rv.headers.add('X-Video-Transcoded', '1')
    return rv


def _has_video_library_access(vid):
    user_id = session.get('user_id')
    role = session.get('role')
    if role == 'admin':
        return True
    if not user_id:
        return False

    from repositories.video_repository import VideoRepository
    from repositories.category_repository import CategoryRepository
    row = VideoRepository.get_video_by_id(vid)
    if not row or not row.get('library_id'):
        return False
    return CategoryRepository.check_user_category_access('video', user_id, row['library_id'])


@video_bp.route('/api/media/videos', methods=['GET'])
@login_required
def list_videos_api():
    """특정 라이브러리에 속한 강좌 카드 목록 조회"""
    library_id = request.args.get('library_id')
    if not library_id:
        return jsonify({'success': False, 'error': 'library_id is required'}), 400

    try:
        library_id_int = int(library_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid library_id'}), 400

    user_id = session.get('user_id')
    role = session.get('role')
    if role != 'admin':
        from repositories.category_repository import CategoryRepository
        if not CategoryRepository.check_user_category_access('video', user_id, library_id_int):
            return jsonify({'success': False, 'error': '영상 강좌 접근 권한이 없습니다.'}), 403

    from repositories.video_repository import VideoRepository
    rows = VideoRepository.list_videos_by_library(library_id_int)
    return jsonify({'success': True, 'videos': rows})


@video_bp.route('/api/media/videos/<int:vid>', methods=['GET'])
@login_required
def get_video_detail_api(vid):
    """강좌 상세(메타 + 에피소드 목록) 조회"""
    if not _has_video_library_access(vid):
        return jsonify({'success': False, 'error': '영상 강좌 접근 권한이 없습니다.'}), 403

    from repositories.video_repository import VideoRepository
    row = VideoRepository.get_video_by_id(vid)
    if not row:
        return jsonify({'success': False, 'error': 'Video not found'}), 404

    episodes = VideoRepository.get_video_episodes(vid)
    return jsonify({'success': True, 'meta': row, 'episodes': episodes})


@video_bp.route('/api/media/videos/<int:vid>/cover', methods=['GET'])
def get_video_cover(vid):
    """강좌 대표 포스터 이미지 서빙"""
    if not _has_video_library_access(vid):
        return jsonify({'success': False, 'error': '영상 강좌 접근 권한이 없습니다.'}), 403

    from repositories.video_repository import VideoRepository
    row = VideoRepository.get_video_by_id(vid)

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
    title = row.get('title') if row else 'Video'
    from api.stream import _build_fallback_svg
    svg_data = _build_fallback_svg(title, file_format='video', seed=str(vid))
    return Response(svg_data, mimetype='image/svg+xml')


@video_bp.route('/api/media/videos/<int:vid>/episodes/<int:eid>/stream', methods=['GET'])
@login_required
def stream_video_episode(vid, eid):
    """강좌 특정 에피소드 영상 스트리밍"""
    if not _has_video_library_access(vid):
        return jsonify({'success': False, 'error': '영상 강좌 접근 권한이 없습니다.'}), 403

    from repositories.video_repository import VideoRepository
    row = VideoRepository.get_episode_by_id_and_video_id(eid, vid)

    if not row or not row.get('file_path'):
        return jsonify({'success': False, 'error': 'Episode not found'}), 404

    # Lazy 백필이 아직 처리 전(duration<=0)이라 needs_transcode가 미확정인 경우, "일단 원본
    # 그대로 내보내고 본다"고 낙관하면 EAC3/AC3 등 브라우저 비호환 오디오 파일이 무음으로
    # 재생되는 사고가 난다. 그래서 첫 재생 요청 시점에 즉석(JIT)으로 코덱만 빠르게 확인해서
    # needs_transcode를 확정하고 DB에도 반영한다(이후 요청/Lazy 백필은 이 값을 그대로 재사용).
    if not row.get('needs_transcode') and float(row.get('duration') or 0) <= 0:
        from services.video_scanner import _probe_video_info, is_browser_compatible
        duration, width, height, vcodec, acodec = _probe_video_info(row['file_path'])
        if duration > 0:
            computed_needs_transcode = 0 if is_browser_compatible(row['file_path'], vcodec, acodec) else 1
            try:
                VideoRepository.update_episode_probe_result(eid, vid, duration, width, height, computed_needs_transcode)
            except Exception as e:
                print(f"[Video-Stream] JIT 코덱 분석 결과 저장 실패 (vid={vid} ep={eid}): {e}")
            row['needs_transcode'] = computed_needs_transcode

    if not row.get('needs_transcode'):
        return _send_video_range_response(row['file_path'])

    return _stream_transcoded_video(row['file_path'], vid, eid)


@video_bp.route('/api/media/videos/<int:vid>/episodes/<int:eid>/subtitle', methods=['GET'])
@login_required
def get_video_episode_subtitle(vid, eid):
    """에피소드 자막 사이드카(SMI/SRT/VTT)를 WebVTT로 변환해 서빙한다."""
    if not _has_video_library_access(vid):
        return jsonify({'success': False, 'error': '영상 강좌 접근 권한이 없습니다.'}), 403

    from repositories.video_repository import VideoRepository
    row = VideoRepository.get_episode_by_id_and_video_id(eid, vid)
    if not row or not row.get('subtitle_path'):
        return jsonify({'success': False, 'error': 'Subtitle not found'}), 404

    from services.subtitle_converter import convert_subtitle_to_vtt
    vtt_text = convert_subtitle_to_vtt(row['subtitle_path'])
    if vtt_text is None:
        return jsonify({'success': False, 'error': 'Subtitle conversion failed'}), 500

    return Response(vtt_text, mimetype='text/vtt', content_type='text/vtt; charset=utf-8')


@video_bp.route('/api/media/videos/<int:vid>/progress', methods=['GET', 'POST'])
@login_required
def video_progress_api(vid):
    if not _has_video_library_access(vid):
        return jsonify({'success': False, 'error': '영상 강좌 접근 권한이 없습니다.'}), 403

    user_id = session.get('user_id', 1)
    from repositories.video_repository import VideoRepository

    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        episode_id = data.get('current_episode_id')
        current_time = float(data.get('current_time', 0.0))
        playback_rate = float(data.get('playback_rate', 1.0))
        is_completed = 1 if data.get('is_completed') else 0
        episode_row = None

        if episode_id is not None:
            try:
                episode_id_int = int(episode_id)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': 'Invalid current_episode_id'}), 400

            episode_row = VideoRepository.get_episode_by_id_and_video_id(episode_id_int, vid)
            if not episode_row:
                return jsonify({'success': False, 'error': 'Episode does not belong to video'}), 400
            episode_id = episode_id_int

        total_pct = 100.0 if is_completed else 0.0
        if not is_completed:
            try:
                v_row = VideoRepository.get_video_by_id(vid)
                if v_row and v_row.get('total_duration') and v_row['total_duration'] > 0:
                    total_pct = min(100.0, (current_time / v_row['total_duration']) * 100.0)
            except Exception:
                pass

        try:
            VideoRepository.save_video_progress(vid, user_id, episode_id, current_time, total_pct, playback_rate, is_completed)

            episode_progress_pct = 0.0
            episode_is_completed = 0
            if episode_id is not None and episode_row:
                episode_duration = float(episode_row.get('duration') or 0.0)
                if episode_duration > 0:
                    episode_progress_pct = min(100.0, max(0.0, (current_time / episode_duration) * 100.0))
                    episode_is_completed = 1 if episode_progress_pct >= 95.0 else 0
                if is_completed:
                    episode_progress_pct = 100.0
                    episode_is_completed = 1
                VideoRepository.save_video_episode_progress(
                    vid, user_id, episode_id, current_time, episode_progress_pct, episode_is_completed
                )

            return jsonify({
                'success': True,
                'episode_id': episode_id,
                'episode_progress_pct': episode_progress_pct,
                'episode_is_completed': episode_is_completed,
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        progress_row = VideoRepository.get_video_progress(vid, user_id)
        return jsonify({'success': True, 'progress': progress_row})


def _run_cmd(cmd, timeout=8):
    """서브프로세스를 실행하고 (returncode, 출력) 튜플을 반환. 실행 파일이 없으면 (None, 에러메시지)."""
    try:
        completed = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=timeout, check=False
        )
        return completed.returncode, completed.stdout or ''
    except FileNotFoundError:
        return None, '실행 파일을 찾을 수 없습니다 (PATH 미등록 또는 미설치).'
    except Exception as e:
        return None, str(e)


@video_bp.route('/api/media/videos/check-vaapi', methods=['GET'])
@admin_required
def check_vaapi_support():
    """현재 컨테이너/서버 환경에서 ffmpeg VAAPI 하드웨어 가속 트랜스코딩이 실제로
    가능한지 단계별로 점검한다 (ffmpeg 빌드 지원 여부 -> 인코더 존재 여부 ->
    /dev/dri 디바이스 패스스루 여부 -> vainfo로 드라이버 실동작 확인)."""
    device_path = request.args.get('device', '/dev/dri/renderD128')

    result = {
        'ffmpeg_found': False,
        'hwaccels_supported': False,
        'encoder_available': False,
        'buildconf_enabled': False,
        'device_path': device_path,
        'device_exists': os.path.exists(device_path),
        'vainfo_found': False,
        'vainfo_output': None,
        'overall': 'unavailable',
        'detail': [],
    }

    rc, out = _run_cmd(['ffmpeg', '-hide_banner', '-hwaccels'])
    if rc is None:
        result['detail'].append(f'ffmpeg 실행 실패: {out}')
    else:
        result['ffmpeg_found'] = True
        result['hwaccels_supported'] = 'vaapi' in out.lower()
        result['detail'].append(f"[-hwaccels] {'vaapi 감지됨' if result['hwaccels_supported'] else 'vaapi 미감지'}")

    if result['ffmpeg_found']:
        rc2, out2 = _run_cmd(['ffmpeg', '-hide_banner', '-h', 'encoder=h264_vaapi'])
        result['encoder_available'] = bool(rc2 == 0 and 'Unknown encoder' not in out2 and 'h264_vaapi' in out2)
        result['detail'].append(f"[encoder=h264_vaapi] {'사용 가능' if result['encoder_available'] else '사용 불가'}")

        rc3, out3 = _run_cmd(['ffmpeg', '-hide_banner', '-buildconf'])
        result['buildconf_enabled'] = '--enable-vaapi' in out3
        result['detail'].append(
            f"[buildconf] {'--enable-vaapi 포함' if result['buildconf_enabled'] else '--enable-vaapi 미확인(런타임 동적 로딩 방식일 수 있어 참고용)'}"
        )

    result['detail'].append(
        f"[디바이스] {device_path} {'존재함' if result['device_exists'] else '존재하지 않음 (docker-compose에 /dev/dri 패스스루 필요)'}"
    )

    rc4, out4 = _run_cmd(['vainfo', '--display', 'drm', '--device', device_path])
    if rc4 is None:
        result['detail'].append(f"[vainfo] 실행 불가: {out4} (libva-utils 미설치일 수 있음, 필수는 아님)")
    else:
        result['vainfo_found'] = True
        result['vainfo_output'] = out4.strip()[:2000]
        result['detail'].append(f"[vainfo] 종료코드={rc4}{' (정상)' if rc4 == 0 else ''}")

    if not result['ffmpeg_found']:
        result['overall'] = 'error'
    elif result['device_exists'] and result['encoder_available'] and result['hwaccels_supported']:
        result['overall'] = 'ok' if rc4 == 0 else 'partial'
    else:
        result['overall'] = 'unavailable'

    # 실제 스트리밍 경로(_detect_vaapi_available)가 참조하는 캐시를 이 수동 점검 결과로 갱신한다.
    # 그래야 관리자가 드라이버를 설치/디바이스를 새로 붙인 뒤 "지금 점검"만 눌러도(컨테이너
    # 재시작 없이) 다음 트랜스코딩 요청부터 바로 VAAPI를 타게 된다.
    _vaapi_availability_cache[device_path] = result['overall'] in ('ok', 'partial')

    return jsonify({'success': True, **result})
