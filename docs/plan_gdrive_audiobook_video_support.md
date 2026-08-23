# 구글 드라이브 책 단위 사전복사 — 오디오북/영상 확장 조사 문서 (조사 완료, 미구현)

## 0. 문서 목적 및 현재 상태

이 문서는 **구현 계획이 아니라 조사 결과**다. 2026-08-23, 사용자가 "향후에 지원하긴 해야 하는데, 수정범위를 미리 파악해봐"라고 요청해서 실제 코드를 직접 추적하며 조사했다. **코드는 한 줄도 바뀌지 않았다** — 이 문서에 적힌 파일/라인 번호는 조사 시점(2026-08-23) 기준이며, 이후 리팩터링으로 달라질 수 있다. 다음에 실제로 착수할 때는 아래 내용을 출발점으로 삼되, 인용된 파일/라인이 여전히 유효한지 먼저 확인할 것.

관련 선행 기능: [plan_gdrive_server_side_copy.md](./plan_gdrive_server_side_copy.md)(서버사이드 복사 최초 설계), `guide_plugins.md` §11(현재 구현된 플러그인 API — zip/cbz/epub/txt/pdf 전용이라고 명시돼 있음).

## 1. 배경 — 지금 뭐가 되고 뭐가 안 되는가

**되는 것**: 일반/성인 서재(`general`/`adult` db_type)의 zip/cbz/epub/txt/pdf 도서. 카테고리 물리 경로에 구글 드라이브 공유 링크를 넣으면:
1. `tools/scanner/engine.py`가 스캔 시점에 `fetch_gdrive_folder_files()`로 공유 폴더를 훑어 가상 경로(`gdrive://<folder_id>/<rel_path>/<filename>`, file_id는 `encode_gdrive_file_id()`로 경로 문자열에 인코딩)로 `books.file_path`에 저장한다.
2. 뷰어가 그 책을 열면 `StreamPageService.get_book_file_info()`/`get_file_path()` → `_resolve_gdrive_view_copy()` → `services/gdrive_view_copy_service.py::resolve_viewable_path()`가 호출돼, 아직 복사 안 된 책이면 그 1권만 `rclone_copy_file_by_id()`로 관리자 자신의 드라이브에 서버사이드 복사한 뒤 로컬 rclone 마운트 경로로 바꿔치기해 돌려준다.
3. 이후로는 평범한 로컬 파일이라 기존 zip 오프셋 스트리밍/EPUB/TXT/PDF 파이프라인이 그대로 동작한다.

**안 되는 것**: 오디오북(`audiobook`)과 영상 강좌(`video`) db_type. 카테고리 생성 자체는 **막혀 있지 않다** — `CategoryService._validate_gdrive_requirements()`(`services/category_service.py:209-223`)는 db_type을 전혀 검사하지 않고 리모트/마운트루트만 확인한다. 그래서 관리자가 오디오북 카테고리에 구글 드라이브 공유 링크를 넣고 저장하는 것 자체는 성공한다. 문제는 그 다음부터다.

## 2. 왜 안 되는지 — 실제로 추적한 코드 경로

### 2.1 스캐너: 조용히 0권으로 끝남 (에러 아님, 그냥 아무 일도 안 일어남)

`tools/scanner/core.py`의 스캔 진입 함수(`scan_library` 계열)를 보면:

```python
# tools/scanner/core.py:112-119 (HDD/NAS wake-up 검사 루프)
from utils.drive_helper import is_gdrive_url
failed_paths = []
for path in target_paths:
    if is_gdrive_url(path):
        print(f"[Scanner-WakeUp] 구글 드라이브 웹 공유 링크 감지: '{path}'. 로컬 디스크 Wake-up 검사를 우회합니다.")
        continue
    ...
```

여기까진 gdrive 링크를 인지하고 로컬 디스크 wake-up 검사를 건너뛴다 — **이미 db_type 상관없이 범용으로 동작한다.** 그런데 바로 다음:

```python
# tools/scanner/core.py:151-165
if db_type == 'audiobook':
    from services.audiobook_scanner import scan_audiobook_library
    for target_p in target_paths:
        scan_audiobook_library(target_p, library_id=library_id, force=force)
    return

if db_type == 'video':
    from services.video_scanner import scan_video_library
    for target_p in target_paths:
        scan_video_library(target_p, library_id=library_id, force=force)
    return
```

`target_p`가 gdrive 링크든 로컬 경로든 구분 없이 그대로 `scan_audiobook_library`/`scan_video_library`에 넘긴다. 그런데 그 두 함수의 **맨 첫 줄**이:

```python
# services/audiobook_scanner.py:671-677
def scan_audiobook_library(library_path, library_id=None, force=False):
    if not os.path.exists(library_path):
        print(f"[AudiobookScanner Error] Library path does not exist: {library_path}")
        return 0
```

```python
# services/video_scanner.py:397-403 (동일 패턴)
def scan_video_library(library_path, library_id=None, force=False):
    ...
    if not os.path.exists(library_path):
        ...
```

`library_path`가 `https://drive.google.com/drive/folders/...` 같은 URL 문자열이면 `os.path.exists()`는 항상 `False`를 반환하므로, **여기서 그냥 `return 0`으로 조용히 끝난다.** 에러 로그도 사용자에게 노출되는 실패도 없이, 그냥 스캔 결과가 0권이다. `scan_library_path`(단건/경로 스캔, `tools/scanner/core.py:242-254`)도 동일 패턴.

**단일/경로 스캔(`scan_library_path`)** 쪽은 조금 다르다 — 이쪽은 general/adult용 분기(`tools/scanner/core.py:232-237`)에서 `is_gdrive_url(target_path)`를 미리 확인해서 `os.path.exists` 체크를 건너뛰지만, audiobook/video 분기(`242-254`)는 그 체크 없이 바로 `scan_audiobook_library`/`scan_video_library`를 호출한다 — 어차피 그 안에서 다시 막히므로 결과는 같다(0권).

### 2.2 스트림 라우트: 애초에 gdrive 해석 함수를 호출하지 않음

스캐너 문제를 어떻게든 우회해서 오디오북/영상 DB에 `gdrive://` 형태의 `file_path`가 들어갔다고 가정해도, 재생 시점에 또 막힌다.

```python
# api/routes/audiobook_routes.py:346-359
@audiobook_bp.route('/api/media/audiobooks/<int:aid>/tracks/<int:tid>/stream', methods=['GET'])
@login_required
def stream_audiobook_track(aid, tid):
    ...
    row = AudiobookRepository.get_track_by_id_and_audiobook_id(tid, aid)
    if not row or not row.get('file_path'):
        return jsonify({'success': False, 'error': 'Track not found'}), 404
    return _send_audio_range_response(row['file_path'])
```

`row['file_path']`를 리포지토리에서 바로 읽어 `_send_audio_range_response()`에 그대로 넘긴다 — `is_gdrive_url()` 체크도, `resolve_viewable_path()` 호출도 없다. `_send_audio_range_response()`는 `os.path.exists(file_path)`부터 확인하므로(`audiobook_routes.py:214`) gdrive 가상 경로면 그냥 404가 난다.

일반/성인 서재 쪽(`api/stream.py`)이 이 문제를 어떻게 피하는지 대조해보면 명확하다:

```python
# services/stream_page_service.py:96-106
@staticmethod
def _resolve_gdrive_view_copy(db_type, book_id, file_path, library_id):
    from utils.drive_helper import is_gdrive_url
    if not file_path or not is_gdrive_url(file_path) or library_id is None:
        return file_path
    from repositories.category_repository import CategoryRepository
    from services.gdrive_view_copy_service import resolve_viewable_path
    library = CategoryRepository.get_library_by_id(db_type, library_id)
    return resolve_viewable_path(db_type, book_id, file_path, library)
```

`get_book_file_info()`(72-93)와 `get_file_path()`(341-347)가 매 호출마다 이 함수를 거친다. `api/stream.py`가 파일을 서빙하는 모든 경로(`166, 193, 216, 239, 263, 301, 325, 350`행)는 전부 `StreamService.get_book_file_info`/`get_file_path`를 거치므로 자동으로 이 해석을 통과한다. **오디오북/영상은 이 공통 관문(`StreamPageService`)을 아예 쓰지 않고 각자 자기 리포지토리에서 직접 `file_path`를 읽는 구조라서, gdrive 해석이 끼어들 지점 자체가 없다.**

영상 쪽 스트림 핸들러(`api/routes/video_routes.py`)도 확인했다 — 아래 지점들이 전부 `row['file_path']`를 직접 읽는다:

```python
# api/routes/video_routes.py:348 (기본 조회), 357, 359, 370, 379, 388, 390
if not row or not row.get('file_path'):
    return jsonify({'success': False, 'error': 'Track not found'}), 404
...
if is_browser_compatible(row['file_path'], vcodec, acodec, format_name):
    ...
return _send_video_range_response(row['file_path'])          # 일반 range 스트림
...
return _stream_hls_for_safari(row['file_path'], vid, eid)     # Safari HLS
...
return _stream_transcoded_video(row['file_path'], vid, eid)   # 온더플라이 트랜스코딩
```

영상은 **호출 지점이 4곳**이라 오디오북(1곳)보다 손댈 곳이 많다.

### 2.3 스캐너 쪽 gdrive 코드가 실제로 어떻게 생겼는지 (재사용 가능한 부분)

일반 스캐너(`tools/scanner/engine.py:164-200`)의 gdrive 분기 로직:

```python
from utils.drive_helper import is_gdrive_url
for t_path in target_paths:
    if is_gdrive_url(t_path):
        from utils.drive_helper import fetch_gdrive_folder_files, extract_gdrive_folder_id, encode_gdrive_file_id
        g_files = fetch_gdrive_folder_files(t_path)
        folder_id = extract_gdrive_folder_id(t_path) or 'gdrive_root'

        grouped_files = {}      # v_root(가상 폴더 경로) -> [파일명, ...]
        grouped_file_ids = {}   # v_root -> {파일명: drive file_id}
        for item in g_files:
            fname = item.get('name')
            rel_f = item.get('rel_folder', '')
            if ignore_filter.should_ignore_file(fname, parent_path=rel_f) or ignore_filter.should_ignore_dir(rel_f):
                continue
            v_root = canonical_path(f"gdrive://{folder_id}/{rel_f}") if rel_f else canonical_path(f"gdrive://{folder_id}")
            grouped_files.setdefault(v_root, []).append(fname)
            grouped_file_ids.setdefault(v_root, {})[fname] = item.get('id')

        for v_root, fnames in grouped_files.items():
            file_ids = grouped_file_ids[v_root]
            for fn in fnames:
                found_file_paths.add(encode_gdrive_file_id(join_canonical(v_root, fn), file_ids.get(fn)))
            tasks.append((v_root, fnames, t_path, file_ids))
        continue
```

핵심 재사용 가능 요소: `fetch_gdrive_folder_files()`(재귀적으로 공유 폴더 트리를 훑어 `{name, rel_folder, id}` 목록 반환, `utils/drive_helper.py:149`), `extract_gdrive_folder_id()`, `encode_gdrive_file_id()`/`split_gdrive_file_id()`(가상 경로 문자열에 file_id를 인코딩/디코딩, `353행`/`360행`). 이 4개 함수는 이미 범용이라 오디오북/영상 스캐너에서도 그대로 쓸 수 있다 — **문제는 이 결과를 "책 1권 = 파일 1개"가 아니라 "오디오북 1개 = 파일 여러 개(트랙)", "강좌 1개 = 파일 여러 개(에피소드)"로 그룹핑하는 로직을 새로 짜야 한다는 것**이다. 일반 스캐너의 그룹핑(폴더 단위 = v_root)과 오디오북/영상의 기존 로컬 그룹핑 로직(아래 §2.4)이 개념적으로는 비슷하지만 그대로 재사용은 안 되고, gdrive 버전을 새로 짜야 한다.

### 2.4 오디오북/영상 로컬 스캐너의 기존 그룹핑 방식 (참고용)

```python
# services/audiobook_scanner.py:701-730 (scan_audiobook_library)
for root, dirs, files in os.walk(library_path):
    has_audio_json = 'audio.json' in files
    has_audio_files = any(f.lower().endswith(AUDIO_EXTENSIONS) for f in files)
    if has_audio_json or has_audio_files:
        ...
        aid = scan_and_save_audiobook_folder(root, library_id=library_id)
        ...
        dirs.clear()   # 오디오북 단위를 찾았으므로 그 아래는 더 안 들어감
```

폴더 하나에 오디오 파일(또는 `audio.json`)이 있으면 그 폴더가 "오디오북 1개"이고, 그 안의 파일들이 트랙이 된다. `dirs.clear()`로 하위 폴더는 더 안 들어간다(오디오북 폴더 안에 또 오디오북이 중첩되지 않는다는 가정). 영상 스캐너(`services/video_scanner.py:397-430`)도 동일한 `os.walk` + `os.path.exists` 게이트 + 폴더 단위 그룹핑 패턴이다. gdrive 버전을 만들 때 이 "폴더 = 컨테이너, 파일들 = 자식" 그룹핑 규칙을 `fetch_gdrive_folder_files()`가 돌려주는 `rel_folder` 기준으로 재구현해야 한다.

## 3. 스키마 — 준비된 부분과 진짜 막힌 부분

### 3.1 이미 준비된 것

`database.py`의 `_SCHEMA_SQL`(781-1082행 부근, "4개 미디어 세션(general/adult/audiobook/video) 공용 스키마"라고 주석에 명시)에 `libraries` 테이블(`gdrive_copy_remote`/`gdrive_view_local_mirror_path` 컬럼 포함, 794-811행)과 `gdrive_book_copies` 테이블(1072-1081행)이 **이미 4개 db_type 전부에** 생성돼 있다. 즉 카테고리 설정 UI/검증 로직도, 뷰-복사 상태 저장 테이블도 스키마 차원에서는 새로 만들 게 없다.

### 3.2 진짜 막힌 것: `gdrive_book_copies.book_id`의 FK

```sql
-- database.py:1072-1081 (SQLite)
CREATE TABLE IF NOT EXISTS gdrive_book_copies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL UNIQUE REFERENCES books(id),   -- ← 여기
    library_id INTEGER NOT NULL,
    source_file_id TEXT NOT NULL,
    status TEXT NOT NULL,
    local_path TEXT,
    error_message TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

이 SQLite 스키마는 `book_id`가 반드시 그 DB 파일의 로컬 `books` 테이블에 존재하는 id를 가리켜야 한다(외래키 제약). 그리고 이 프로젝트는 FK 강제 적용이 켜져 있다:

```python
# database.py:90
conn.execute("PRAGMA foreign_keys = ON;")
```

오디오북 DB 파일에도 `_SCHEMA_SQL`이 공용으로 적용되니 `books` 테이블 자체는 존재한다 — 하지만 **오디오북 스캐너는 `books` 테이블에 아무것도 쓰지 않는다**(자기 전용 테이블 `audiobooks`/`audiobook_tracks`를 쓴다). 그래서 오디오북 DB의 로컬 `books` 테이블은 사실상 항상 비어 있고, `gdrive_book_copies.book_id`에 `audiobook_tracks.id` 값을 넣으려 하면 그 id가 (텅 빈) `books` 테이블에 없으므로 **FK 위반 에러**가 난다.

반면 MariaDB 쪽 스키마(`tools/db_schema_updater.py:360-370`)는:

```sql
CREATE TABLE IF NOT EXISTS gdrive_book_copies (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL UNIQUE,   -- ← FK 선언 자체가 없음
    library_id BIGINT NOT NULL,
    ...
```

**FK가 아예 없다.** 즉 SQLite/MariaDB가 이미 서로 다르게 동작한다(이 기능과 무관하게 존재하던 기존 불일치). MariaDB 설치본에서는 지금 당장 `audiobook_tracks.id`를 `gdrive_book_copies.book_id`에 넣어도 에러는 안 나지만, "책"이 아닌 걸 `book_id`라는 이름의 컬럼에 넣는 의미론적 혼란은 남는다.

### 3.3 권장 방향 (결정 안 됨, 다음 세션에서 판단)

- **안 A (최소 변경)**: SQLite의 FK 제약을 제거하는 마이그레이션(테이블 재생성 필요, SQLite는 `ALTER TABLE ... DROP CONSTRAINT` 미지원)만 하고, `gdrive_book_copies`를 오디오북/영상에도 그대로 재사용(`book_id`에 track_id/episode_id를 그냥 넣음). 코드량은 적지만 컬럼명이 계속 오해를 부름.
- **안 B (구조적으로 깔끔)**: `gdrive_audiobook_track_copies`, `gdrive_video_episode_copies` 테이블을 새로 만든다. 이 프로젝트가 이미 `books`/`audiobooks+audiobook_tracks`/`videos+video_episodes`로 미디어 타입별 테이블을 분리해둔 기존 패턴과 일관성이 있다. `repositories/{sqlite,mariadb}/gdrive_book_copy_repository.py`도 미디어 타입별로 분리하거나, `entity_table` 파라미터를 받는 형태로 일반화해야 한다.
- 어느 쪽이든 `services/gdrive_view_copy_service.py::resolve_viewable_path()` 자체는 수정 없이 그대로 쓸 수 있다 — 이 함수는 리포지토리 호출부(`GdriveBookCopyRepository.get_by_book_id`/`upsert_copied`/`upsert_unsupported`)를 통해서만 이 테이블과 상호작용하므로, 안 B를 택해도 그 리포지토리의 내부 구현만 바뀌고 함수 시그니처는 그대로 유지 가능.

## 4. 메타데이터 추출 — 오디오는 가능, 영상은 근본적으로 어려움

### 4.1 오디오: Range 읽기로 가능 (새 코드 필요하지만 막힌 건 아님)

```python
# services/audiobook_scanner.py:48-63 (get_audio_duration_and_size)
def get_audio_duration_and_size(file_path, file_size=None, remote_fast_path=False):
    ...
    if file_path.lower().endswith('.mp3'):
        return estimate_mp3_duration(file_path, file_size, remote_fast_path=remote_fast_path), file_size
    # 이후 mutagen/tinytag/ffprobe 순으로 시도 — 전부 로컬 파일 경로를 직접 연다
```

이 함수는 로컬 파일 바이트를 직접 읽는다 — gdrive 가상 경로로는 호출 불가능. 하지만 이 프로젝트에는 이미 **부분 다운로드 없이 Range 요청만으로 파일 일부를 읽는 재사용 가능한 원시 함수**가 있다:

```python
# utils/drive_helper.py:510-553 (zip 오프셋 스캔에 쓰이는 기존 함수들)
def fetch_gdrive_zip_offsets(file_id, initial_tail=65536, max_tail=8 * 1024 * 1024): ...
def fetch_gdrive_page_bytes(file_id, header_offset, compress_size): ...
```

이건 zip 중앙 디렉토리를 전체 다운로드 없이 꼬리(tail) 부분만 Range로 읽어오는 데 쓰이고 있다(메모리 `[[project_gdrive_link_registration_status]]`가 언급하는 "scan-time `_compute_offsets()` (Range-based, no download)"가 바로 이거다). MP3의 ID3v2 태그는 파일 앞부분에, ID3v1은 마지막 128바이트에 있으므로, `fetch_gdrive_page_bytes(file_id, 0, N)`(앞부분) + 필요시 꼬리 부분을 읽는 조합으로 **전체 다운로드 없이 태그/추정 duration을 얻는 새 함수**(`fetch_gdrive_audio_header_bytes()` 같은 이름)를 만들 수 있다. **막혀 있는 게 아니라 아직 안 짜여 있을 뿐.**

### 4.2 영상: 근본적으로 어려움

영상은 `ffprobe`로 코덱/해상도/길이를 뽑는데, 이건 컨테이너 포맷에 따라 메타데이터(moov atom 등)가 파일 맨 끝에 있는 경우가 흔하다(특히 스트리밍 최적화 안 된 mp4). Range 읽기 하나로 안정적으로 해결이 안 된다. ffprobe가 URL을 직접 열어 필요한 부분만 HTTP Range로 당겨오는 것도 이론적으로 가능은 하지만(ffmpeg의 http protocol이 Range를 지원), 이건 "구글 드라이브 access token을 매번 새로 발급해서 ffprobe에 넘기는" 별도 인증/URL 서명 계층이 필요해 상당히 큰 별도 작업이다.

**현실적인 절충안**: 스캔 시점엔 파일명 기반 제목만 등록하고 길이/코덱은 `unknown` 상태로 두었다가, **그 에피소드가 실제로 처음 복사(시청 or `/prefetch` 호출)된 뒤에야** 로컬 사본에 대해 기존 `ffprobe` 파이프라인을 그대로 돌려 채워 넣는 방식. 이건 이미 이 프로젝트가 "gdrive 책의 커버 없으면 폴백 SVG로 영구히 둔다"([[project_gdrive_link_registration_status]] 2026-08-22 섹션 참고, `tools/lazy_scanner.py::get_series_cover_fallback_single()`가 gdrive 책에 대해 다운로드 폴백을 의도적으로 껐음)고 받아들인 것과 같은 종류의 트레이드오프다. **다만 이건 엔지니어링 문제가 아니라 "길이/코덱 unknown 상태의 영상 카드가 목록에 떠도 괜찮은가"라는 제품 판단이 먼저 필요하다.**

## 5. 스트림/뷰-복사 레이어 — 필요한 변경

### 5.1 변경 불필요한 부분

```python
# services/gdrive_view_copy_service.py:114-116
def resolve_viewable_path(db_type, book_id, file_path, library):
    """gdrive:// 가상 경로를, 이미 복사된 로컬 경로(또는 아직 미지원인 경우 원본)로 바꿔 반환한다."""
```

이 함수는 `db_type`/`book_id`/`file_path`/`library` 네 값만으로 완전히 동작하는 범용 함수다(락, TTL, mirror_root 계산 전부 `db_type`을 매개변수로만 다룬다). §3의 스키마 문제만 해결되면(리포지토리 내부 구현만 바뀜, 함수 시그니처는 유지 가능) **이 함수 자체는 수정 없이 오디오북/영상에도 그대로 쓸 수 있다.**

TTL 정리 잡(`cleanup_stale_view_copies()`, `services/gdrive_view_copy_service.py:236-258`)도 이미 `scheduler_service.py`에서 4개 db_type 전부를 순회하도록 등록돼 있다(오디오북/영상 지원이 실제로 켜지면 자동으로 같이 청소됨, 추가 배선 불필요).

### 5.2 변경 필요한 부분

- `api/routes/audiobook_routes.py::stream_audiobook_track()`(346-359행) + `audiobook_track_transcode_status()`(361-380행 부근): `row['file_path']`를 쓰기 전에 `StreamPageService._resolve_gdrive_view_copy()`와 동등한 호출 삽입. 오디오북은 `book_id` 자리에 `track_id`(또는 §3.3에서 정한 키)를 넘겨야 함.
- `api/routes/video_routes.py`: 4개 호출 지점(§2.2 참고) 전부 동일 처리 필요. HLS 생성(`_stream_hls_for_safari`)은 로컬 파일을 전제로 세그먼트를 미리 만드는 구조라, gdrive 원본을 그대로 못 넣고 반드시 로컬 사본이 있어야 함 — 즉 HLS 경로는 "복사 완료 후에만" 접근 가능하도록 강제해야 할 수 있음(첫 진입 시 동기 대기 UX 설계 필요).

## 6. 상대적 작업량 및 순서 권고

| 항목 | 오디오북 | 영상 |
|---|---|---|
| 스트림 라우트 변경 지점 | 1곳 | 4곳 (일반/트랜스코딩/HLS/프로브) |
| 메타데이터(길이/코덱) 사전 추출 | Range 읽기로 가능(새 코드 필요) | 사실상 불가능, "첫 시청 후에만 채움"으로 타협 필요 |
| 그룹핑 단위 | 폴더=오디오북, 파일=트랙 | 폴더=강좌, 파일=에피소드 (유사) |
| 이 기능이 원래 다루던 단위와의 유사성 | "1책=1파일"에 가까움(멀티트랙이라도 트랙 단위론 1:1) | 동일하게 "1에피소드=1파일"이라 구조적으로는 비슷 |

**결론**: 오디오북이 더 작고 리스크가 낮다. 영상은 스트림 경로가 4배 많고, 메타데이터 문제는 엔지니어링이 아니라 제품 결정이 선행돼야 한다. **오디오북을 먼저 템플릿으로 구현하고, 거기서 얻은 gdrive 그룹핑/스캐너 패턴을 영상에 재적용하는 순서를 권장.**

## 7. 미해결 질문 (다음 세션에서 결정 필요)

1. §3.3의 안 A(FK 제거) vs 안 B(테이블 분리) — 어느 쪽으로 갈지.
2. 영상 메타데이터 unknown 상태를 UI에서 어떻게 보여줄지(플레이스홀더 길이 "??:??", 코덱 배지 숨김 등) — 제품 결정.
3. 오디오북 폴더 하나에 트랙이 매우 많을 때(예: 100+ 트랙 오디오북), 그 폴더를 처음 열 때 트랙 전체를 한꺼번에 복사할지, 재생되는 트랙만 그때그때 복사할지 — 후자가 기존 "책 1권" 철학과 일관되지만, 오디오북은 이어듣기가 잦아 트랙 넘어갈 때마다 복사 대기가 생기는 UX 트레이드오프가 있음.
4. 영상 HLS 경로는 로컬 사본을 반드시 요구하므로, 첫 재생 시 "복사 중..." 대기 UX를 어떻게 설계할지(현재 zip/epub 등은 동기 대기가 짧아 문제 없었지만, 영상 파일은 훨씬 커서 서버사이드 복사 자체는 빨라도 로컬 마운트 가시성 폴링 타임아웃(§`_wait_for_local_visibility`, 기본 6초)이 부족할 가능성).
5. §3.2에서 지적한 SQLite/MariaDB FK 불일치는 이 기능과 무관하게 이미 존재하던 기존 버그성 불일치다 — 이번 확장과 별개로 독립적으로 고칠지도 판단 필요.

## 8. 참고: 조사에 사용한 핵심 함수/파일 인덱스

- `utils/drive_helper.py`: `fetch_gdrive_folder_files()`(149), `extract_gdrive_folder_id()`(99), `encode_gdrive_file_id()`/`split_gdrive_file_id()`(353/360), `fetch_gdrive_zip_offsets()`/`fetch_gdrive_page_bytes()`(510/537, Range 읽기 원시 함수), `is_gdrive_url()`(593), `has_gdrive_share_line()`(607).
- `tools/scanner/core.py`: HDD wake-up 루프(112-146), audiobook/video 분기(151-165, 242-254).
- `tools/scanner/engine.py`: 일반 스캐너 gdrive 그룹핑 로직(164-200).
- `services/audiobook_scanner.py`: `scan_audiobook_library()`(671-751), `get_audio_duration_and_size()`(48-95).
- `services/video_scanner.py`: `scan_video_library()`(397 부근).
- `services/gdrive_view_copy_service.py`: `resolve_viewable_path()`(114-233), `cleanup_stale_view_copies()`(236-258) — 전부 재사용 가능, 수정 불필요.
- `services/stream_page_service.py`: `_resolve_gdrive_view_copy()`(96-106) — 오디오북/영상에 이식할 패턴의 원본.
- `api/routes/audiobook_routes.py`: `stream_audiobook_track()`(346-359), `audiobook_track_transcode_status()`(361행 부근).
- `api/routes/video_routes.py`: 스트림/트랜스코딩/HLS/프로브 4개 호출 지점.
- `database.py`: `_SCHEMA_SQL`(781행 부근, `libraries`/`gdrive_book_copies` 정의 포함), `PRAGMA foreign_keys = ON`(90).
- `tools/db_schema_updater.py`: MariaDB용 `gdrive_book_copies`(360-370, FK 없음).
