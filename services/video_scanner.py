# -*- coding: utf-8 -*-
import os
import json
import re
import subprocess
import time
import html

import yaml

from services.audiobook_scanner import natural_sort_key

from utils import media_types as _media_types
VIDEO_EXTENSIONS = _media_types.VIDEO_EXTENSIONS

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

# 파일명 앞의 "S01E02." / "S01E02 - " 접두어를 제거하기 위한 정규식 (show.yaml 매칭 실패 시 title fallback용)
EPISODE_PREFIX_RE = re.compile(r'^\s*S\d+E\d+\s*(?:[.\-–_:]\s*)?', re.IGNORECASE)

# 강좌 폴더 안 대표 이미지 이름(우선순위 순). 없으면 폴더의 첫 이미지 파일을 쓴다(오디오북과 같은 규칙).
FOLDER_POSTER_NAMES = (
    'poster.jpg', 'cover.jpg', 'folder.jpg', 'poster.png', 'cover.png', 'folder.png',
    'poster.jpeg', 'cover.jpeg', 'folder.jpeg', 'poster.webp', 'cover.webp', 'folder.webp',
)


# 브라우저가 별도 트랜스코딩 없이 <video> 태그로 직접 재생 가능한 컨테이너/코덱 조합.
# mkv는 Chrome/Edge 계열에서 h264+aac 조합이면 대체로 잘 재생되지만, Safari는 MKV
# 컨테이너 자체를 지원하지 않는다 - 사용자가 이 트레이드오프를 인지하고 mkv를 호환
# 목록에 포함하기로 결정함(2026-08-17).
#
# [2026-08-17 후속] 예상대로 Safari/iOS에서 mkv 재생이 아예 안 된다는 리포트가 실제로
# 들어왔다. 이 needs_transcode 플래그는 요청자 브라우저와 무관하게 DB에 전역 1개 값으로
# 저장되므로, 여기서 policy를 다시 좁히는 대신 api/routes/video_routes.py::
# stream_video_episode()에서 요청 시점에 User-Agent로 Safari/iOS를 감지해 mkv 파일만
# 강제로 트랜스코딩 폴백으로 돌리도록 처리했다(_is_safari_or_ios()). 즉 이 상수 자체는
# 그대로 두고(Chrome/Edge는 여전히 트랜스코딩 없이 직접 재생), 브라우저별 예외를
# 라우트 레이어에서 흡수하는 방식으로 재검토를 마쳤다.
BROWSER_COMPATIBLE_CONTAINERS = {'mp4', 'm4v', 'webm', 'mkv'}
BROWSER_COMPATIBLE_VIDEO_CODECS = {'h264', 'vp8', 'vp9'}
BROWSER_COMPATIBLE_AUDIO_CODECS = {'aac', 'opus', 'vorbis', 'mp3'}

# 확장자가 주장하는 컨테이너와 ffprobe가 실측한 실제 컨테이너(format_name)가 일치하는지
# 검증하기 위한 힌트. 2026-08-17 실사용자 리포트로 발견: 인프런 등 강좌 플랫폼 다운로드
# 도구가 실제로는 MPEG-TS 스트림인 파일을 확장자만 `.mp4`로 잘못 저장하는 경우가 다수
# 있었다(ffprobe format_name이 'mpegts'로 나옴). 코덱(h264/aac)은 정상이라 확장자+코덱만
# 보던 기존 판정으로는 "호환"으로 오판했고, Chrome/Edge는 이 컨테이너 불일치에 관대해
# 우연히 재생됐지만 Safari/iOS는 엄격하게 거부(MediaError code 4)했다.
CONTAINER_FORMAT_NAME_HINTS = {
    'mp4': ('mp4',),
    'm4v': ('mp4',),
    'webm': ('webm', 'matroska'),
    'mkv': ('matroska',),
}


def _first_str(value):
    """YAML 값이 목록이면 첫 문자열, 문자열이면 그대로(공백 제거), 그 밖에는 ''."""
    if isinstance(value, list):
        value = next((v for v in value if isinstance(v, str) and v.strip()), '')
    return value.strip() if isinstance(value, str) else ''


def _pick_folder_poster_name(file_names):
    """강좌 폴더(최상위) 파일 이름 목록에서 대표 이미지 이름. 없으면 ''."""
    by_lower = {name.lower(): name for name in file_names}
    for cand in FOLDER_POSTER_NAMES:
        if cand in by_lower:
            return by_lower[cand]
    for name in sorted(file_names, key=natural_sort_key):
        if name.lower().endswith(_media_types.IMAGE_EXTENSIONS):
            return name
    return ''


def _pick_course_poster(top_level_names, course_meta, metadata_cover_url, has_file):
    """포스터 우선순위: 폴더 이미지(poster.jpg 등) → show.yaml art/posters(URL 또는 강좌 폴더 기준 상대 파일명)
    → metadata.json cover_url. 폴더 이미지를 먼저 쓰는 이유: 외부 이미지 주소가 바뀌거나 막혀도 그대로 보이고,
    사용자가 바꾼 그림이 바로 반영된다.
    반환: ('file', 강좌 폴더 기준 상대 경로) / ('url', 주소) / (None, ''). has_file(rel)로 상대 파일 존재를 확인한다
    (로컬은 파일 시스템, 구글 링크는 목록)."""
    folder_poster = _pick_folder_poster_name(top_level_names)
    if folder_poster:
        return 'file', folder_poster
    for key in ('art', 'posters'):
        value = (course_meta or {}).get(key) or ''
        if not value:
            continue
        if value.startswith(('http://', 'https://')):
            return 'url', value
        rel = value.replace('\\', '/').lstrip('/')
        if rel and '..' not in rel.split('/') and has_file(rel):
            return 'file', rel
    if metadata_cover_url:
        return 'url', metadata_cover_url
    return None, ''


def _load_course_metadata_json(folder_path, file_names):
    """윌라 영상 강좌 metadata.json(web_id/cid/title/cover_url/clips[num,title,duration])에서
    포스터 URL과 회차 제목만 꺼낸다: (cover_url, {num: title}). 없거나 형식이 다르면 ('', {})."""
    if 'metadata.json' not in {n.lower() for n in file_names}:
        return '', {}
    from services.audiobook_scanner import load_json_any_encoding
    try:
        data, _ = load_json_any_encoding(os.path.join(folder_path, 'metadata.json'))
    except Exception as err:
        print(f"[VideoScanner Warning] metadata.json read error in {folder_path}: {err}")
        return '', {}
    if not isinstance(data, dict):
        return '', {}
    cover_url = _first_str(data.get('cover_url'))
    if not cover_url.startswith(('http://', 'https://')):
        cover_url = ''
    clip_titles = {}
    clips = data.get('clips')
    if isinstance(clips, list):
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            try:
                num = int(clip.get('num'))
            except (TypeError, ValueError):
                continue
            title = html.unescape(_first_str(clip.get('title')))
            if title:
                clip_titles[num] = title
    return cover_url, clip_titles


def _resolve_course_poster(folder_path, file_names, course_meta, metadata_cover_url):
    """로컬 강좌 폴더의 포스터 소스(로컬 경로 또는 URL). 우선순위는 _pick_course_poster()."""
    kind, value = _pick_course_poster(file_names, course_meta, metadata_cover_url,
                                      lambda rel: os.path.isfile(os.path.join(folder_path, rel)))
    if kind == 'file':
        return os.path.normpath(os.path.join(folder_path, value))
    return value


def is_browser_compatible(file_path, vcodec, acodec, container_format_name=None):
    """컨테이너 확장자 + 비디오/오디오 코덱 + (제공 시) 실제 컨테이너 포맷이 브라우저
    네이티브 재생 가능 조합인지 판단. container_format_name은 ffprobe format.format_name
    실측값 — 확장자와 실제 포맷이 어긋나는(예: mpegts를 .mp4로 잘못 저장) 파일을 걸러낸다."""
    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    if ext not in BROWSER_COMPATIBLE_CONTAINERS:
        return False
    if vcodec and vcodec not in BROWSER_COMPATIBLE_VIDEO_CODECS:
        return False
    if acodec and acodec not in BROWSER_COMPATIBLE_AUDIO_CODECS:
        return False
    if container_format_name:
        hints = CONTAINER_FORMAT_NAME_HINTS.get(ext)
        if hints and not any(hint in container_format_name for hint in hints):
            return False
    return True


def _probe_video_info(file_path):
    """
    ffprobe로 duration(초) + 비디오 스트림 width/height + 비디오/오디오 코덱명 +
    실제 컨테이너 포맷명(format_name)을 한 번에 조회합니다.
    실패 시 (0.0, 0, 0, '', '', '')을 반환합니다.
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'stream=codec_type,codec_name,width,height',
            '-show_entries', 'format=duration,format_name',
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
            return 0.0, 0, 0, '', '', ''

        data = json.loads(completed.stdout)
        fmt = data.get('format') or {}
        duration = float(fmt.get('duration') or 0.0)
        format_name = str(fmt.get('format_name') or '')
        streams = data.get('streams') or []
        vstream = next((s for s in streams if s.get('codec_type') == 'video'), {}) or {}
        astream = next((s for s in streams if s.get('codec_type') == 'audio'), {}) or {}
        width = int(vstream.get('width') or 0)
        height = int(vstream.get('height') or 0)
        vcodec = str(vstream.get('codec_name') or '').lower()
        acodec = str(astream.get('codec_name') or '').lower()
        return duration, width, height, vcodec, acodec, format_name
    except Exception:
        return 0.0, 0, 0, '', '', ''


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

    # show.yaml은 강좌 플랫폼 웹페이지에서 제목/설명을 긁어오는 외부(커뮤니티) 도구가 생성하는
    # 경우가 많은데, 그런 도구 상당수가 HTML 엔티티(&lt; &amp; &#x27; 등)를 디코딩하지 않고
    # 원문 그대로 저장한다. html.unescape()는 엔티티가 없는 일반 텍스트에는 영향이 없으므로,
    # 안전하게 방어적으로 적용해 "&lt;강좌명&gt;" 같은 원문 노출을 막는다.
    genres = data.get('genres', [])
    course_meta = {
        'title': html.unescape(str(data.get('title', '')).strip()),
        'genres': ", ".join(genres) if isinstance(genres, list) else str(genres or ''),
        'summary': html.unescape(str(data.get('summary', '')).strip()),
        'art': _first_str(data.get('art')),
        'posters': _first_str(data.get('posters')),
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
                    'title': html.unescape(str(ep.get('title', '')).strip()),
                    'originally_available_at': str(ep.get('originally_available_at', '')).strip(),
                }
        # 시즌 자체의 art가 있으면 최상위 art보다 우선
        if not course_meta['art']:
            course_meta['art'] = _first_str(season0.get('art'))

    return course_meta, episode_by_index


def _episode_code_and_title(fname, idx, episode_by_index, clip_titles):
    """회차 코드와 제목: (episode_code, title, premiered). 제목은 show.yaml → metadata.json clips → 파일명 순.
    번호는 파일명의 SxxExx(없으면 정렬 순서 idx)로 show.yaml/clips와 연결한다."""
    m = EPISODE_CODE_RE.search(fname)
    if m:
        ep_num = int(m.group(2))
        episode_code = f"S{int(m.group(1)):02d}E{ep_num:02d}"
    else:
        ep_num = idx
        episode_code = ''
    ep_meta = episode_by_index.get(ep_num, {})
    title = ep_meta.get('title', '') or clip_titles.get(ep_num, '')
    if not title:
        stripped = EPISODE_PREFIX_RE.sub('', fname)
        title = os.path.splitext(stripped)[0].strip() or fname
    return episode_code, title, ep_meta.get('originally_available_at', '')


def _course_meta_dict(course_meta, folder_name, folder_path, poster):
    return {
        'title': (course_meta or {}).get('title') or folder_name,
        'sort_title': '',
        'web_id': (course_meta or {}).get('code', ''),
        'genres': (course_meta or {}).get('genres', ''),
        'poster': poster,
        'backdrop': (course_meta or {}).get('art', ''),
        'premiered': '',
        'description': (course_meta or {}).get('summary', ''),
        'folder_name': folder_name,
        'folder_path': folder_path,
    }


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
    try:
        top_level_files = [n for n in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, n))]
    except OSError:
        top_level_files = []
    metadata_cover_url, clip_titles = _load_course_metadata_json(folder_path, top_level_files)

    meta = _course_meta_dict(course_meta, folder_name, os.path.normpath(folder_path),
                             _resolve_course_poster(folder_path, top_level_files, course_meta, metadata_cover_url))

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

        episode_code, title, premiered = _episode_code_and_title(fname, idx, episode_by_index, clip_titles)

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

        if existing and int(existing.get('is_deleted') or 0):
            VideoRepository.set_deleted(existing['id'], False)
            print(f"[VideoScanner][RESTORED] video_id={existing['id']} folder_path={normalized_folder_path}")
        scan_result = VideoRepository.save_video_scan(normalized_folder_path, library_id, meta, episodes)
        video_id = scan_result['video_id']
        from services.audiobook_scanner import _touch_if_poster_replaced
        _touch_if_poster_replaced(VideoRepository, video_id, meta.get('poster'), 'video', library_id)

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
    changed = 0
    moved = 0
    errors = 0
    skip_existing = not force
    library_started_at = time.perf_counter()

    from repositories.video_repository import VideoRepository
    from services.audiobook_scanner import _audio_signature, _MovedAudiobookFinder, _hide_unmatched_missing
    folder_rows = VideoRepository.get_folder_rows(library_id)
    # 숨겨진(폴더가 사라졌던) 강좌는 '등록됨'으로 보지 않는다 - 폴더가 다시 나타나면 처리되며 복원된다
    existing_folder_paths = {os.path.normpath(str(r['folder_path'])) for r in folder_rows if not r.get('is_deleted')}
    # 폴더 이름 변경/이동 인식과 사라진 강좌 숨김은 오디오북과 같은 규칙(회차 상대 경로+크기가 모두 있으면 같은 강좌)
    moved_finder = _MovedAudiobookFinder(library_path, folder_rows,
                                         load_tracks=VideoRepository.get_video_episodes, extensions=VIDEO_EXTENSIONS)
    # 등록된 강좌도 파일 목록(상대 경로+크기)을 DB 회차와 비교해 달라진 강좌(회차 추가/삭제·이름 변경)만 다시
    # 처리한다 - 예전엔 등록된 강좌를 통째로 건너뛰어 새 회차가 강제 재스캔 전까지 등록되지 않았다.
    episode_signatures = VideoRepository.get_episode_signatures(library_id) if skip_existing else {}

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
            folder = os.path.normpath(root)
            if skip_existing and folder in existing_folder_paths and \
                    set(_audio_signature(root, VIDEO_EXTENSIONS)) != episode_signatures.get(folder, set()):
                changed += 1
                print(f"[VideoScanner][CHANGED] library_id={library_id} reason=file_list_changed folder_path={folder}")
            elif skip_existing and folder in existing_folder_paths:
                skipped += 1
                dirs.clear()
                continue

            if folder not in existing_folder_paths:
                match = moved_finder.find(root)
                if match:
                    row, episode_paths = match
                    VideoRepository.relocate_video(row['id'], folder, os.path.basename(folder), episode_paths)
                    moved_finder.moved_ids.add(row['id'])
                    moved += 1
                    print(f"[VideoScanner][MOVED] video_id={row['id']} from={row['folder_path']} to={folder}")

            vid = scan_and_save_video_folder(root, library_id=library_id)
            if vid:
                count += 1
                dirs.clear()
            else:
                errors += 1

    hidden = _hide_unmatched_missing(moved_finder, library_path, library_id,
                                     db_type='video', repo=VideoRepository, log_prefix='VideoScanner')

    library_elapsed_ms = int((time.perf_counter() - library_started_at) * 1000)
    print(
        "[VideoScanner][LIBRARY_SCAN_DONE] "
        f"library_id={library_id} "
        f"processed={count} "
        f"skipped={skipped} "
        f"changed={changed} "
        f"moved={moved} "
        f"hidden={hidden} "
        f"errors={errors} "
        f"force={force} "
        f"elapsed_ms={library_elapsed_ms} "
        f"library_path={library_path}"
    )
    return count



# ── 구글 드라이브 공유 링크 카테고리 (GDRIVE_LINK_BETA) ─────────────────────────────────────────────
# 1단계: 등록만 한다(목록·메타·포스터). 회차 파일은 읽지 않고 길이 0으로 두며, 재생은 아직 지원하지 않는다.
# 회차 file_path는 도서와 같은 가상 경로(gdrive:/<공유 폴더 ID>/<상대 경로>?gid=<파일 ID>)이고,
# lazy_scanner의 ffprobe·컨테이너 재검사 대상에서 빠진다(원격 영상을 받지 않음).

GDRIVE_VIDEO_LIST_EXTENSIONS = VIDEO_EXTENSIONS + _media_types.METADATA_EXTENSIONS + _media_types.IMAGE_EXTENSIONS


def _gdrive_course_path(folder_id, rel_folder):
    return f"gdrive:/{folder_id}/{rel_folder}" if rel_folder else f"gdrive:/{folder_id}"


def _group_gdrive_courses(g_files):
    """목록을 강좌별로 묶는다: {강좌 상대 폴더: [항목...]}. 로컬 규칙과 같게 영상 파일이 직접 든 폴더 중
    가장 위의 것이 강좌이고, 그 아래 하위 폴더의 파일(회차·이미지·메타)은 그 강좌에 합친다."""
    video_dirs = {(it.get('rel_folder') or '') for it in g_files
                  if (it.get('name') or '').lower().endswith(VIDEO_EXTENSIONS)}

    def course_of(rel_folder):
        parts = [p for p in (rel_folder or '').split('/') if p]
        for i in range(len(parts) + 1):
            cand = '/'.join(parts[:i])
            if cand in video_dirs:
                return cand
        return None

    courses = {}
    for it in g_files:
        course = course_of(it.get('rel_folder') or '')
        if course is not None:
            courses.setdefault(course, []).append(it)
    return courses


def _rel_in_course(course_rel, item):
    rel_folder = item.get('rel_folder') or ''
    sub = rel_folder[len(course_rel):].lstrip('/') if course_rel else rel_folder
    return f"{sub}/{item['name']}" if sub else item['name']


def _gdrive_episode_path(course_path, course_rel, item):
    from utils.drive_helper import encode_gdrive_file_id
    return encode_gdrive_file_id(f"{course_path}/{_rel_in_course(course_rel, item)}", item.get('id'))


def _gdrive_episode_signature(course_path, paths_and_sizes):
    """VideoRepository.get_episode_signatures()와 같은 방식으로 계산한 회차 서명."""
    base = os.path.normpath(course_path)
    return {(os.path.relpath(os.path.normpath(p), base), int(size or 0)) for p, size in paths_and_sizes}


def _download_gdrive_poster(remote, item, dest_path):
    """포스터 이미지 하나를 받는다(목록의 수정 시각과 같으면 다시 받지 않음). 성공하면 dest_path, 실패하면 ''."""
    from utils.drive_helper import drive_modtime_epoch
    from utils.rclone_gdrive_copy import rclone_download_file_by_id
    remote_mtime = drive_modtime_epoch(item.get('modifiedTime'))
    try:
        if remote_mtime is not None and abs(os.path.getmtime(dest_path) - remote_mtime) < 2:
            return dest_path
    except OSError:
        pass
    try:
        rclone_download_file_by_id(remote, item['id'], dest_path)
        if remote_mtime is not None:
            os.utime(dest_path, (remote_mtime, remote_mtime))
        return dest_path
    except Exception as err:
        print(f"[VideoScanner Warning] gdrive poster download failed: {dest_path} - {err}")
        return ''


def parse_gdrive_video_course(folder_id, course_rel, items, meta_mirror_root, poster_root, remote):
    """링크 공유 폴더의 강좌 하나를 로컬 parse_video_folder()와 같은 형태로 만든다. 영상 파일은 읽지 않는다."""
    from utils.drive_helper import drive_modtime_epoch
    course_path = _gdrive_course_path(folder_id, course_rel)
    folder_name = course_rel.rsplit('/', 1)[-1] if course_rel else folder_id
    by_rel = {_rel_in_course(course_rel, it): it for it in items if it.get('name')}

    mirror_dir = os.path.join(meta_mirror_root, *course_rel.split('/')) if course_rel else meta_mirror_root
    course_meta, episode_by_index = _load_show_yaml(mirror_dir) if os.path.isdir(mirror_dir) else (None, {})
    try:
        mirror_names = [n for n in os.listdir(mirror_dir) if os.path.isfile(os.path.join(mirror_dir, n))]
    except OSError:
        mirror_names = []
    metadata_cover_url, clip_titles = _load_course_metadata_json(mirror_dir, mirror_names)

    top_level_names = [rel for rel in by_rel if '/' not in rel]
    kind, value = _pick_course_poster(top_level_names, course_meta, metadata_cover_url, lambda rel: rel in by_rel)
    poster = ''
    if kind == 'url':
        poster = value
    elif kind == 'file':
        poster_root_real = os.path.realpath(poster_root)
        dest = os.path.normpath(os.path.join(poster_root, *course_rel.split('/'), *value.split('/')))
        # 공유 폴더의 이름은 남이 정한다 - 포스터 폴더 밖에 쓰지 않게 막는다
        if os.path.commonpath([poster_root_real, os.path.realpath(dest)]) == poster_root_real:
            poster = _download_gdrive_poster(remote, by_rel[value], dest)
        if not poster and metadata_cover_url:
            poster = metadata_cover_url

    videos = sorted((rel for rel in by_rel if rel.lower().endswith(VIDEO_EXTENSIONS)),
                    key=lambda rel: natural_sort_key(rel.rsplit('/', 1)[-1]))
    episodes = []
    for idx, rel in enumerate(videos, start=1):
        it = by_rel[rel]
        fname = it['name']
        episode_code, title, premiered = _episode_code_and_title(fname, idx, episode_by_index, clip_titles)
        episodes.append({
            'episode_number': idx,
            'episode_code': episode_code,
            'title': title,
            'filename': fname,
            'file_path': _gdrive_episode_path(course_path, course_rel, it),
            'file_mtime': float(drive_modtime_epoch(it.get('modifiedTime')) or 0.0),
            'file_size': int(it.get('size') or 0),
            'duration': 0.0,
            'width': 0,
            'height': 0,
            'premiered': premiered,
            'format': os.path.splitext(fname)[1].lstrip('.').lower(),
            'subtitle_path': '',
        })

    meta = _course_meta_dict(course_meta, folder_name, course_path, poster)
    meta['total_duration'] = 0.0
    meta['total_episodes'] = len(episodes)
    return {'meta': meta, 'episodes': episodes}


def _poster_kind(poster):
    if not poster:
        return 'none'
    return 'url' if poster.startswith(('http://', 'https://')) else 'file'


def scan_video_library_gdrive(share_url, library_id=None, force=False):
    """구글 드라이브 공유 링크 영상 카테고리 스캔(등록만). 카테고리의 rclone 리모트로 목록을 한 번 받고,
    show.yaml/metadata.json은 메타 미러로, 포스터 이미지는 강좌마다 한 장만 받는다. 반환: 처리한 강좌 수."""
    from utils.drive_helper import (extract_gdrive_folder_id, fetch_gdrive_folder_files_via_rclone,
                                    gdrive_meta_mirror_dir, refresh_gdrive_meta_mirror, GDRIVE_META_EXTENSIONS)
    from utils.gdrive_beta_log import beta_log
    from services.system_health_service import SystemHealthService
    from repositories.category_repository import CategoryRepository
    from repositories.video_repository import VideoRepository
    from services.audiobook_scanner import _touch_if_poster_replaced

    started = time.perf_counter()
    folder_id = extract_gdrive_folder_id(share_url)
    library = CategoryRepository.get_library_by_id('video', library_id) if library_id is not None else None
    remote = (library or {}).get('gdrive_copy_remote')
    if not folder_id or not remote:
        print(f"[VideoScanner Error] gdrive link category needs a folder link and a connected rclone remote: "
              f"library_id={library_id} remote={remote!r} link={share_url}")
        return 0

    print(f"[VideoScanner][LIBRARY_SCAN_START] library_id={library_id} force={force} gdrive=1 folder_id={folder_id}")
    listing_health = (f'gdrive_listing:video:{library_id}', f'구글 링크 목록 조회 (video 카테고리 {library_id})')
    t_list = time.time()
    try:
        g_files = fetch_gdrive_folder_files_via_rclone(remote, share_url, extensions=GDRIVE_VIDEO_LIST_EXTENSIONS)
    except Exception as err:
        # 부분 목록으로 숨김 처리를 하면 안 되므로 이번 스캔은 아무것도 바꾸지 않는다.
        print(f"[VideoScanner Error] gdrive listing failed: library_id={library_id} - {err}")
        beta_log('scan.listing_failed', db='video', lib=library_id, remote=remote, took=time.time() - t_list, err=err)
        SystemHealthService.record_failure(*listing_health, err)
        return 0
    beta_log('scan.listing', db='video', lib=library_id, via='rclone', files=len(g_files), errors=0,
             took=time.time() - t_list)
    SystemHealthService.record_success(listing_health[0])

    courses = _group_gdrive_courses(g_files)
    base_dir = gdrive_meta_mirror_dir('video', library_id)
    meta_mirror_root = os.path.join(base_dir, folder_id)
    poster_root = os.path.join(base_dir, '_posters', folder_id)

    # 메타 파일은 강좌 폴더 최상위의 것만 받는다(공유 폴더의 다른 yaml/json까지 받지 않게).
    meta_items = [it for course_rel, items in courses.items() for it in items
                  if (it.get('rel_folder') or '') == course_rel
                  and (it.get('name') or '').lower().endswith(GDRIVE_META_EXTENSIONS)]
    if meta_items:
        meta_health = (f'gdrive_meta:video:{library_id}', f'구글 링크 메타데이터 받기 (video 카테고리 {library_id})')
        t_meta = time.time()
        try:
            fetched, failed, mode = refresh_gdrive_meta_mirror(remote, folder_id, meta_mirror_root, meta_items)
            beta_log('scan.meta_mirror', db='video', lib=library_id, mode=mode, fetched=fetched, failed=failed,
                     took=time.time() - t_meta)
            if failed:
                SystemHealthService.record_failure(*meta_health, f'{failed}개 메타데이터 파일을 받지 못함 ({mode})')
            else:
                SystemHealthService.record_success(meta_health[0])
        except Exception as err:
            # 미러가 없어도 강좌 등록은 진행한다(폴더 이름·파일명으로) - 다음 스캔에서 다시 받는다.
            print(f"[VideoScanner Warning] gdrive metadata mirror failed: {err}")
            beta_log('scan.meta_mirror_failed', db='video', lib=library_id, took=time.time() - t_meta, err=err)
            SystemHealthService.record_failure(*meta_health, err)

    prefix = os.path.normpath(_gdrive_course_path(folder_id, ''))
    folder_rows = [r for r in VideoRepository.get_folder_rows(library_id)
                   if os.path.normpath(str(r['folder_path'])) == prefix
                   or os.path.normpath(str(r['folder_path'])).startswith(prefix + os.sep)]
    existing = {os.path.normpath(str(r['folder_path'])) for r in folder_rows if not r.get('is_deleted')}
    signatures = VideoRepository.get_episode_signatures(library_id) if not force else {}

    count = skipped = changed = errors = 0
    found = set()
    for course_rel in sorted(courses, key=natural_sort_key):
        items = courses[course_rel]
        course_path = _gdrive_course_path(folder_id, course_rel)
        key = os.path.normpath(course_path)
        found.add(key)
        if not force and key in existing:
            current = _gdrive_episode_signature(course_path, [
                (_gdrive_episode_path(course_path, course_rel, it), it.get('size'))
                for it in items if (it.get('name') or '').lower().endswith(VIDEO_EXTENSIONS)])
            if current == signatures.get(key, set()):
                skipped += 1
                continue
            changed += 1
            print(f"[VideoScanner][CHANGED] library_id={library_id} reason=file_list_changed folder_path={course_path}")
        try:
            result = parse_gdrive_video_course(folder_id, course_rel, items, meta_mirror_root, poster_root, remote)
            row = VideoRepository.get_by_folder_path(course_path)
            if row and int(row.get('is_deleted') or 0):
                VideoRepository.set_deleted(row['id'], False)
                print(f"[VideoScanner][RESTORED] video_id={row['id']} folder_path={course_path}")
            saved = VideoRepository.save_video_scan(course_path, library_id, result['meta'], result['episodes'])
            poster = result['meta'].get('poster') or ''
            _touch_if_poster_replaced(VideoRepository, saved['video_id'], poster, 'video', library_id)
            count += 1
            print(f"[VideoScanner][COURSE_PROCESSED] video_id={saved['video_id']} title={result['meta']['title']} "
                  f"episodes={len(result['episodes'])} poster={_poster_kind(poster)} gdrive=1 folder_path={course_path}")
        except Exception as err:
            errors += 1
            print(f"[VideoScanner ERROR] Failed to save gdrive video course {course_path}: {err}")

    # 목록에서 사라진 강좌는 숨긴다(목록을 정상으로 받았을 때만, 한 번에 많이 사라지면 보류).
    missing = [r for r in folder_rows
               if not r.get('is_deleted') and os.path.normpath(str(r['folder_path'])) not in found]
    hidden = 0
    if missing:
        from services.scan_problem_service import is_mass_missing
        if is_mass_missing('video', library_id, len(missing), len(folder_rows)):
            print(f"[VideoScanner][MISSING_HELD] library_id={library_id} reason=mass_missing "
                  f"missing={len(missing)} total={len(folder_rows)} gdrive=1")
        else:
            for r in missing:
                if VideoRepository.set_deleted(r['id'], True):
                    hidden += 1
                    print(f"[VideoScanner][MISSING_HIDDEN] video_id={r['id']} folder_path={r['folder_path']}")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    beta_log('scan.summary', db='video', lib=library_id, courses=len(courses), processed=count, skipped=skipped,
             hidden=hidden, errors=errors, took=elapsed_ms / 1000)
    print(f"[VideoScanner][LIBRARY_SCAN_DONE] library_id={library_id} processed={count} skipped={skipped} "
          f"changed={changed} moved=0 hidden={hidden} errors={errors} force={force} gdrive=1 elapsed_ms={elapsed_ms}")
    return count
