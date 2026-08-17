# -*- coding: utf-8 -*-
"""
video_hls_service.py - Safari/iOS 전용 HLS(m3u8) 온디맨드 트랜스코딩 생성 관리

iOS Safari의 기본 <video> 재생 엔진(MSE 없이 src= 직결)은 Content-Length가 없는
청크 스트림 + fragmented MP4(우리의 기존 pipe:1 트랜스코딩 방식)를 사실상 지원하지
않는다(MediaError code 4, MEDIA_ERR_SRC_NOT_SUPPORTED). 반면 HLS는 Apple이 만든
포맷이라 Safari 네이티브 <video src="....m3u8">만으로 완벽 지원된다.

세그먼트를 디스크(cache/hls/<episode_id>/)에 점진적으로 생성하며(event playlist),
플레이어는 표준 HLS 방식대로 .m3u8을 주기적으로 재요청해 새 세그먼트를 발견한다.
Chrome/Edge/Android는 기존 pipe 트랜스코딩 경로를 그대로 쓰므로 영향 없다.
"""
import os
import re
import subprocess
import threading
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HLS_CACHE_DIR = os.path.join(BASE_DIR, 'cache', 'hls')
os.makedirs(HLS_CACHE_DIR, exist_ok=True)

_SEGMENT_NAME_RE = re.compile(r'^seg\d{5}\.ts$')

# 에피소드별 생성 상태를 프로세스 메모리에서 추적(단일 gunicorn 워커 프로세스 전제 -
# 이 앱은 --workers 1로 운영되므로 충분하다. 다중 워커로 바뀌면 파일 락 등으로 교체 필요).
_generation_lock = threading.Lock()
_active_processes = {}  # episode_id -> subprocess.Popen


def _episode_cache_dir(episode_id):
    d = os.path.join(HLS_CACHE_DIR, str(episode_id))
    os.makedirs(d, exist_ok=True)
    return d


def _playlist_path(episode_id):
    return os.path.join(_episode_cache_dir(episode_id), 'playlist.m3u8')


def _read_playlist(episode_id):
    path = _playlist_path(episode_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def is_generation_complete(episode_id):
    content = _read_playlist(episode_id)
    return bool(content and '#EXT-X-ENDLIST' in content)


def is_generation_active(episode_id):
    proc = _active_processes.get(episode_id)
    return proc is not None and proc.poll() is None


def ensure_hls_generation(episode_id, file_path, use_vaapi, device_path, extra_args):
    """이 에피소드의 HLS 생성을 보장한다. 이미 완료됐거나 진행 중이면 아무 것도 하지 않고
    반환하며, 없으면 새로 ffmpeg를 백그라운드로 기동한다."""
    with _generation_lock:
        if is_generation_complete(episode_id) or is_generation_active(episode_id):
            return

        cache_dir = _episode_cache_dir(episode_id)
        # 이전 시도의 불완전한 잔재(중단된 세그먼트/플레이리스트) 정리 후 새로 시작
        for name in os.listdir(cache_dir):
            try:
                os.remove(os.path.join(cache_dir, name))
            except Exception:
                pass

        pre_input_args = ['-vaapi_device', device_path] if use_vaapi else []
        cmd = (
            ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'warning']
            + pre_input_args
            + ['-i', file_path]
            + extra_args
            + [
                '-f', 'hls',
                '-hls_time', '6',
                '-hls_list_size', '0',
                '-hls_flags', 'independent_segments',
                '-hls_playlist_type', 'event',
                '-hls_segment_filename', os.path.join(cache_dir, 'seg%05d.ts'),
                os.path.join(cache_dir, 'playlist.m3u8'),
            ]
        )
        print(f"[Video-HLS][ep={episode_id}] 생성 시작 mode={'vaapi' if use_vaapi else 'cpu'} cmd={' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        _active_processes[episode_id] = proc

        def _relay_stderr():
            try:
                for line in iter(proc.stderr.readline, b''):
                    if not line:
                        break
                    print(f"[Video-HLS][ep={episode_id}] {line.decode('utf-8', errors='replace').rstrip()}")
            except Exception:
                pass

        threading.Thread(target=_relay_stderr, daemon=True).start()


def wait_for_playlist(episode_id, timeout=20.0, poll_interval=0.3):
    """최소 1개 세그먼트가 포함된 플레이리스트가 생성될 때까지 대기 후 내용을 반환한다.
    타임아웃 시 그 시점까지 있는 내용을 그대로 반환(없으면 None) - 플레이어가 이후
    재요청 시 이어서 채워진 상태를 받게 된다."""
    deadline = time.time() + timeout
    last_content = None
    while time.time() < deadline:
        content = _read_playlist(episode_id)
        if content and '#EXTINF' in content:
            return content
        last_content = content
        time.sleep(poll_interval)
    return last_content


def get_segment_path(episode_id, segment_name):
    """경로 탈출 방지를 위해 세그먼트 파일명을 엄격히 검증한 뒤 실제 경로를 반환한다."""
    if not _SEGMENT_NAME_RE.match(segment_name or ''):
        return None
    path = os.path.join(_episode_cache_dir(episode_id), segment_name)
    if os.path.exists(path):
        return path
    return None


def rewrite_playlist_segment_urls(manifest_text, segment_base_url):
    """ffmpeg가 세그먼트를 상대 파일명(seg00000.ts)으로 기록한 m3u8을, 우리 세그먼트
    서빙 라우트의 절대 URL로 치환한다(플레이리스트 자체가 /stream 경로에서 나가므로
    상대 경로 해석이 우리 라우팅 구조와 안 맞음)."""
    def _replace(match):
        return segment_base_url + match.group(1)

    return re.sub(r'^(seg\d{5}\.ts)$', _replace, manifest_text, flags=re.MULTILINE)
