# -*- coding: utf-8 -*-
import os
import json
import re
import subprocess
import time

import yaml

from services.audiobook_scanner import natural_sort_key

VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.webm', '.mov', '.m4v', '.ts')

# 자막 사이드카 탐색 확장자 (같은 파일명, 확장자만 다른 파일을 우선순위 순으로 찾음)
SUBTITLE_EXTENSIONS = ('.smi', '.srt', '.vtt')


def _find_sidecar_subtitle(file_path):
    """
    영상 파일과 같은 basename의 자막 사이드카를 찾는다. 단순 <base>.<ext> 뿐 아니라
    <base>.<lang>.<ext>, <base>.<lang>.forced.<ext> 같은 언어 태그 붙은 실제 배포 관행
    (예: Movie.mp4 + Movie.ko.srt + Movie.ko.forced.srt)도 인식한다.
    우선순위: forced(대사 일부만 있는 부분자막) 제외 > 한국어(ko/kor) 우선 > 확장자 선호(srt>smi>vtt).
    """
    folder = os.path.dirname(file_path)
    video_basename = os.path.basename(file_path)
    base = os.path.splitext(video_basename)[0]

    try:
        entries = os.listdir(folder)
    except OSError:
        return None

    ext_priority = {'.srt': 0, '.smi': 1, '.vtt': 2}
    ranked = []
    for fname in entries:
        # base 뒤에 반드시 '.'이 와야 함 (예: "Lecture.1" 이 "Lecture.10.ko.srt"에 우연히
        # 매칭되는 접두어 충돌을 방지)
        if fname == video_basename or not fname.startswith(base + '.'):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in SUBTITLE_EXTENSIONS:
            continue

        stem = fname[:-len(ext)]
        tags = [t.lower() for t in stem[len(base):].split('.') if t]
        is_forced = 'forced' in tags
        is_korean = 'ko' in tags or 'kor' in tags
        priority = (1 if is_forced else 0, 0 if is_korean else 1, ext_priority.get(ext, 9))
        ranked.append((priority, os.path.join(folder, fname)))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0])
    return ranked[0][1]

# S01E01 형식의 시즌/에피소드 번호 (Plex/Kodi TV쇼 명명 규칙)
EPISODE_CODE_RE = re.compile(r'S(\d+)E(\d+)', re.IGNORECASE)

# 파일명 앞의 "S01E02." 접두어를 제거하기 위한 정규식 (show.yaml 매칭 실패 시 title fallback용)
EPISODE_PREFIX_RE = re.compile(r'^\s*S\d+E\d+\.\s*', re.IGNORECASE)

# 브라우저가 별도 트랜스코딩 없이 <video> 태그로 직접 재생 가능한 컨테이너/코덱 조합.
# mkv는 Chrome/Edge 계열에서 h264+aac 조합이면 대체로 잘 재생되지만, Safari는 MKV
# 컨테이너 자체를 지원하지 않는다 - 사용자가 이 트레이드오프를 인지하고 mkv를 호환
# 목록에 포함하기로 결정함(2026-08-17). Safari에서 mkv 재생이 안 되는 리포트가 오면
# 이 결정을 재검토할 것.
BROWSER_COMPATIBLE_CONTAINERS = {'mp4', 'm4v', 'webm', 'mkv'}
BROWSER_COMPATIBLE_VIDEO_CODECS = {'h264', 'vp8', 'vp9'}
BROWSER_COMPATIBLE_AUDIO_CODECS = {'aac', 'opus', 'vorbis', 'mp3'}


def is_browser_compatible(file_path, vcodec, acodec):
    """컨테이너 확장자 + 비디오/오디오 코덱이 브라우저 네이티브 재생 가능 조합인지 판단."""
    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    if ext not in BROWSER_COMPATIBLE_CONTAINERS:
        return False
    if vcodec and vcodec not in BROWSER_COMPATIBLE_VIDEO_CODECS:
        return False
    if acodec and acodec not in BROWSER_COMPATIBLE_AUDIO_CODECS:
        return False
    return True


def _probe_video_info(file_path):
    """
    ffprobe로 duration(초) + 비디오 스트림 width/height + 비디오/오디오 코덱명을 한 번에 조회합니다.
    실패 시 (0.0, 0, 0, '', '')을 반환합니다.
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'stream=codec_type,codec_name,width,height',
            '-show_entries', 'format=duration',
            '-of', 'json',
            file_path,
        ]
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout:
            return 0.0, 0, 0, '', ''

        data = json.loads(completed.stdout)
        duration = float((data.get('format') or {}).get('duration') or 0.0)
        streams = data.get('streams') or []
        vstream = next((s for s in streams if s.get('codec_type') == 'video'), {}) or {}
        astream = next((s for s in streams if s.get('codec_type') == 'audio'), {}) or {}
        width = int(vstream.get('width') or 0)
        height = int(vstream.get('height') or 0)
        vcodec = str(vstream.get('codec_name') or '').lower()
        acodec = str(astream.get('codec_name') or '').lower()
        return duration, width, height, vcodec, acodec
    except Exception:
        return 0.0, 0, 0, '', ''


def _load_show_yaml(folder_path):
    """
    show.yaml(Plex TV쇼 NFO 스타일 사이드카)이 있으면 파싱해서
    (course_meta_dict, episode_meta_by_index) 튜플을 반환합니다.
    없거나 파싱 실패 시 (None, {}).

    멀티 시즌은 1단계에서 미지원 — seasons[0]만 사용합니다.
    """
    yaml_path = os.path.join(folder_path, 'show.yaml')
    if not os.path.exists(yaml_path):
        return None, {}

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    except Exception as err:
        print(f"[VideoScanner Warning] show.yaml read error in {folder_path}: {err}")
        return None, {}

    if not isinstance(data, dict):
        return None, {}

    genres = data.get('genres', [])
    course_meta = {
        'title': str(data.get('title', '')).strip(),
        'genres': ", ".join(genres) if isinstance(genres, list) else str(genres or ''),
        'summary': str(data.get('summary', '')).strip(),
        'art': str(data.get('art', '')).strip(),
        'posters': str(data.get('posters', '')).strip(),
        'code': str(data.get('code', '')).strip(),
    }

    episode_by_index = {}
    seasons = data.get('seasons', [])
    if isinstance(seasons, list) and seasons:
        season0 = seasons[0] if isinstance(seasons[0], dict) else {}
        episodes = season0.get('episodes', [])
        if isinstance(episodes, list):
            for ep in episodes:
                if not isinstance(ep, dict):
                    continue
                try:
                    idx = int(ep.get('index'))
                except (TypeError, ValueError):
                    continue
                episode_by_index[idx] = {
                    'title': str(ep.get('title', '')).strip(),
                    'originally_available_at': str(ep.get('originally_available_at', '')).strip(),
                }
        # 시즌 자체의 art가 있으면 최상위 art보다 우선
        if not course_meta['art']:
            course_meta['art'] = str(season0.get('art', '')).strip()

    return course_meta, episode_by_index


def parse_video_folder(folder_path, existing_episode_cache=None):
    """
    단일 강좌(코스) 디렉터리를 분석하여 메타데이터 및 에피소드 목록을 파싱합니다.
    audiobook_scanner.parse_audiobook_folder()와 동일한 반환 형태를 사용합니다.
    """
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return None

    folder_name = os.path.basename(os.path.normpath(folder_path))
    video_files = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(VIDEO_EXTENSIONS):
                full_path = os.path.normpath(os.path.join(root, file))
                video_files.append(full_path)

    if not video_files:
        return None

    video_files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))

    course_meta, episode_by_index = _load_show_yaml(folder_path)

    meta = {
        'title': (course_meta or {}).get('title') or folder_name,
        'sort_title': '',
        'web_id': (course_meta or {}).get('code', ''),
        'genres': (course_meta or {}).get('genres', ''),
        'poster': (course_meta or {}).get('art') or (course_meta or {}).get('posters', ''),
        'backdrop': (course_meta or {}).get('art', ''),
        'premiered': '',
        'description': (course_meta or {}).get('summary', ''),
        'folder_name': folder_name,
        'folder_path': os.path.normpath(folder_path),
    }

    episodes = []
    total_duration = 0.0
    duration_cache_hits = 0
    file_probe_hits = 0
    episode_cache = existing_episode_cache or {}

    for idx, fpath in enumerate(video_files, start=1):
        fname = os.path.basename(fpath)
        normalized_path = os.path.normpath(fpath)

        try:
            stat_info = os.stat(fpath)
            file_size = int(stat_info.st_size)
            file_mtime = float(stat_info.st_mtime)
        except Exception:
            file_size = 0
            file_mtime = 0.0

        m = EPISODE_CODE_RE.search(fname)
        if m:
            season_num = int(m.group(1))
            ep_num = int(m.group(2))
            episode_code = f"S{season_num:02d}E{ep_num:02d}"
        else:
            ep_num = idx
            episode_code = ''

        ep_meta = episode_by_index.get(ep_num, {})
        title = ep_meta.get('title', '')
        if not title:
            stripped = EPISODE_PREFIX_RE.sub('', fname)
            title = os.path.splitext(stripped)[0].strip() or fname
        premiered = ep_meta.get('originally_available_at', '')

        # duration/width/height는 여기서 ffprobe로 동기 추출하지 않는다 (원격 드라이브에서 파일당
        # 수 초씩 걸려 스캔 전체가 매우 느려짐 - Plex/Jellyfin처럼 "발견"과 "분석"을 분리).
        # 파일이 그대로면(size/mtime 동일) 기존 값(이미 lazy 백필됐다면 실제값, 아니면 0)을 유지하고,
        # 신규/변경 파일은 0으로 두어 tools/lazy_scanner.py가 백그라운드에서 채우도록 한다.
        cache_row = episode_cache.get(normalized_path)
        if (
            cache_row and
            int(cache_row.get('file_size', -1)) == int(file_size) and
            int(float(cache_row.get('file_mtime', -1.0) or -1.0)) == int(file_mtime)
        ):
            duration = float(cache_row.get('duration', 0.0) or 0.0)
            width = int(cache_row.get('width', 0) or 0)
            height = int(cache_row.get('height', 0) or 0)
            duration_cache_hits += 1
        else:
            duration, width, height = 0.0, 0, 0
            file_probe_hits += 1

        total_duration += duration
        ext = os.path.splitext(fname)[1].lstrip('.').lower()
        subtitle_path = _find_sidecar_subtitle(fpath) or ''

        episodes.append({
            'episode_number': idx,
            'episode_code': episode_code,
            'title': title,
            'filename': fname,
            'file_path': fpath,
            'file_mtime': file_mtime,
            'file_size': file_size,
            'duration': duration,
            'width': width,
            'height': height,
            'premiered': premiered,
            'format': ext,
            'subtitle_path': subtitle_path,
        })

    meta['total_duration'] = total_duration
    meta['total_episodes'] = len(episodes)

    return {
        'meta': meta,
        'episodes': episodes,
        'duration_cache_hits': duration_cache_hits,
        'file_probe_hits': file_probe_hits,
    }


def scan_and_save_video_folder(folder_path, library_id=None):
    """
    단일 강좌 폴더를 스캔하여 비디오 DB에 저장/업데이트합니다.
    """
    from repositories.video_repository import VideoRepository

    started_at = time.perf_counter()

    try:
        normalized_folder_path = os.path.normpath(folder_path)

        if library_id is not None:
            from repositories.category_repository import CategoryRepository
            if not CategoryRepository.get_library_by_id('video', library_id):
                library_id = None

        existing = VideoRepository.get_by_folder_path(normalized_folder_path)
        existing_episode_cache = {}
        if existing:
            for r in VideoRepository.get_video_episodes(existing['id']):
                if not r or not r.get('file_path'):
                    continue
                key = os.path.normpath(str(r['file_path']))
                existing_episode_cache[key] = {
                    'file_mtime': float(r.get('file_mtime') or 0.0),
                    'file_size': int(r.get('file_size') or 0),
                    'duration': float(r.get('duration') or 0.0),
                    'width': int(r.get('width') or 0),
                    'height': int(r.get('height') or 0),
                }

        result = parse_video_folder(folder_path, existing_episode_cache=existing_episode_cache)
        if not result:
            return None

        meta = result['meta']
        episodes = result['episodes']

        scan_result = VideoRepository.save_video_scan(normalized_folder_path, library_id, meta, episodes)
        video_id = scan_result['video_id']

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        print(
            "[VideoScanner][COURSE_PROCESSED] "
            f"video_id={video_id} "
            f"title={meta['title']} "
            f"episodes={len(episodes)} "
            f"duration_cache_hits={result.get('duration_cache_hits', 0)} "
            f"pending_lazy_analysis={result.get('file_probe_hits', 0)} "
            f"episode_inserts={scan_result.get('episode_inserts', 0)} "
            f"episode_updates={scan_result.get('episode_updates', 0)} "
            f"episode_deletes={scan_result.get('episode_deletes', 0)} "
            f"duration_sec={meta['total_duration']:.1f} "
            f"elapsed_ms={elapsed_ms} "
            f"folder_path={meta['folder_path']}"
        )
        return video_id
    except Exception as err:
        print(f"[VideoScanner ERROR] Failed to save video course {folder_path}: {err}")
        return None


def scan_video_library(library_path, library_id=None, force=False):
    """
    상위 비디오 라이브러리 디렉토리를 순회하며 모든 강좌(코스) 폴더를 스캔합니다.
    오디오북과 동일하게 "폴더 하나 = 강좌 하나" 규칙을 적용합니다
    (강좌 폴더를 찾으면 그 하위 디렉터리는 더 이상 내려가지 않음).
    """
    if not os.path.exists(library_path):
        print(f"[VideoScanner Error] Library path does not exist: {library_path}")
        return 0

    count = 0
    skipped = 0
    errors = 0
    skip_existing = not force
    library_started_at = time.perf_counter()

    from repositories.video_repository import VideoRepository
    raw_paths = VideoRepository.get_folder_paths(library_id)
    existing_folder_paths = {os.path.normpath(str(p)) for p in raw_paths if p}

    print(
        "[VideoScanner][LIBRARY_SCAN_START] "
        f"library_id={library_id} "
        f"force={force} "
        f"existing_records={len(existing_folder_paths)} "
        f"library_path={library_path}"
    )

    for root, dirs, files in os.walk(library_path):
        has_video_files = any(f.lower().endswith(VIDEO_EXTENSIONS) for f in files)

        if has_video_files:
            if skip_existing and os.path.normpath(root) in existing_folder_paths:
                skipped += 1
                dirs.clear()
                continue

            vid = scan_and_save_video_folder(root, library_id=library_id)
            if vid:
                count += 1
                dirs.clear()
            else:
                errors += 1

    library_elapsed_ms = int((time.perf_counter() - library_started_at) * 1000)
    print(
        "[VideoScanner][LIBRARY_SCAN_DONE] "
        f"library_id={library_id} "
        f"processed={count} "
        f"skipped={skipped} "
        f"errors={errors} "
        f"force={force} "
        f"elapsed_ms={library_elapsed_ms} "
        f"library_path={library_path}"
    )
    return count
