# 🗄️ 데이터베이스 스키마 명세

BookOasis는 **SQLite(기본값)** 와 **MariaDB/MySQL** 두 엔진을 지원하며, 두 경우 모두 같은 테이블·컬럼 구성을 씁니다. `.env`의 `DB_ENGINE`(`sqlite` 또는 `mariadb`)으로 고릅니다.

- **SQLite 모드**: **DB 파일 4개**
  - 일반 `db/media_general.db`, 성인 `db/media_adult.db`, 오디오북 `db/media_audiobook.db`, 영상 `db/media_video.db`
- **MariaDB 모드**: **데이터베이스 4개** — `media_general`, `media_adult`, `media_audiobook`, `media_video`
  - 접두어 `media_`는 `MARIADB_DATABASE_PREFIX`로 바꿀 수 있습니다.
  - 전환 절차는 [move_to_mariadb.md](./move_to_mariadb.md), [guide_admin.md](./guide_admin.md) 8절 참고

4개 DB 모두 **같은 전체 테이블 세트**가 만들어집니다. 예를 들어 `video` DB에도 `books`가, `general` DB에도 `videos`가 (비어 있는 채로) 있습니다. 실제로 쓰이는 테이블은 DB 종류에 따라 다르며 2절 표의 "쓰는 DB" 열에 적었습니다.

이 문서는 테이블의 **역할과 관계**를 정리합니다. 컬럼 타입·기본값의 기준은 코드입니다(6절). 테이블 목록은 `tests/test_spec_db_schema_tables.py`가 코드와 비교하므로, 테이블을 추가·삭제하면 이 문서 2절도 함께 고쳐야 테스트가 통과합니다.

---

## 1. 스키마 개요

- 스키마 원본은 두 곳입니다: SQLite `services/db_migration_service.py`의 `_SCHEMA_SQL`, MariaDB `services/schema_mariadb.py`의 `MARIADB_CENTRAL_SCHEMA`. 두 곳의 테이블 구성은 같아야 합니다(테스트가 확인).
- 기동 때 `run_full_migration()`이 4개 DB에 같은 스키마를 적용하고, 선언에 있는데 운영 DB에 없는 컬럼·인덱스를 보강합니다(SQLite는 `_SCHEMA_SQL`을 읽어 자동 보강, MariaDB는 `services/db_migration_service.py`의 `_ensure_mariadb_columns`/`_ensure_mariadb_indexes` 보강 목록).
- 과거 버전에서 올라온 운영 DB에는 잔여 컬럼·인덱스가 남아 있을 수 있으므로, 코어/플러그인 쿼리는 호환성을 고려해야 합니다.
- MariaDB는 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin`을 쓰며, SQLite의 `INTEGER`/`TEXT`는 대체로 `BIGINT`/`VARCHAR(n)` 또는 `TEXT`로 옮겨집니다.
- 전역 데이터(설정, 스캔 대기열·이력, 알림, MCP 대기 변경, kosync, 사용자별 설정)는 **general DB 하나에만** 씁니다. `users`는 4개 DB에 같은 사용자 이름으로 복제됩니다.

---

## 2. 공통 테이블 목록

4개 DB 공통 테이블 45개입니다. "쓰는 DB"는 실제로 데이터가 쌓이는 DB입니다.

| 묶음 | 테이블 | 쓰는 DB |
| :--- | :--- | :--- |
| 카테고리 | `library_groups`, `library_kinds`, `libraries`, `plugin_group_assignments` | 4개 모두 (각 DB가 자기 카테고리) |
| 도서 | `books`, `book_offsets`, `series_summary`, `series_summary_state` | general, adult |
| 오디오북·음악 | `audiobooks`, `audiobook_tracks`, `audiobook_progress`, `audiobook_track_progress`, `audiobook_music_lookups` | audiobook |
| 영상 | `videos`, `video_episodes`, `video_progress`, `video_episode_progress` | video |
| 사용자·진행률 | `users`, `user_category_permissions` | 4개 모두 |
| | `user_progress`, `user_reading_log`, `user_favorites` | general, adult |
| | `user_settings` | general |
| 읽기 부가 | `book_annotations`, `epub_bookmarks`, `tts_progress` | general, adult |
| 컬렉션 | `collections`, `collection_items` | 4개 모두 (요청의 `db_type` 세션별) |
| TTS 미리 만들기 | `tts_audio_books`, `tts_audio_pieces`, `tts_pregen_jobs` | general, adult |
| | `tts_audio_cache` | 쓰지 않음 (v2.7.9 예전 캐시 색인, 비우기만 함) |
| 구글 링크 | `gdrive_book_copies` | general, adult |
| 외부 연동 | `kosync_credentials`, `kosync_documents`, `kosync_progress` | general |
| | `mcp_pending_changes` | general |
| 스캐너 | `scanner_tasks`, `scan_history` | general (대상 DB는 `kwargs.db_type`) |
| | `scanner_progress`, `folder_mtimes` | 각 카테고리의 DB |
| 설정·플러그인 | `settings`, `plugin_load_events` | general |
| 알림·문제 기록 | `problem_occurrences`, `problem_groups` | general (대상 DB는 `db_type` 컬럼) |

---

## 3. 테이블 상세

### library_groups

라이브러리를 묶는 상위 그룹(사이드바 폴더 그룹핑).

- PK: `id`
- 컬럼: `name`, `icon`, `color`, `sort_order`

### library_kinds

카테고리 속성(만화/도서/잡지 등)의 종류 목록. 세션(DB)마다 하나이며 관리자가 정의한다.

- PK: `code` (소문자 slug, `^[a-z][a-z0-9_-]{0,23}$`, 만든 뒤 변경 불가)
- 컬럼: `name`(표시 이름, UNIQUE, 25자 이내), `is_builtin`, `sort_order`
- 기본 종류 4개(`manga`/`novel`/`book`/`magazine`)는 일반·성인 DB에만 시딩되며(`is_builtin=1`) 이름만 변경할 수 있고 삭제할 수 없다. 오디오북 DB에는 기본 종류 `music`(음악)이 시딩되며, 이 속성의 카테고리는 음악 모드(폴더=앨범, 곡 태그 표시)로 스캔된다. 영상 DB는 빈 목록으로 시작한다.

### libraries

라이브러리 루트 및 스캔 설정.

- PK: `id`
- 주요 FK: `group_id -> library_groups.id`
- 컬럼: `name`, `physical_path`, `cron_schedule`, `schedule_enabled`, `last_scanned_at`, `scan_status`, `is_remote`, `vfs_refresh_before_scan`, `rclone_rc_url`, `icon`, `color`, `hide_cover`, `hide_title`, `cover_aspect_ratio`, `content_kind`, `group_id`, `sort_order`, `gdrive_copy_remote`, `gdrive_view_local_mirror_path`, `pending_delete`, `transfer_target_id`
- `schedule_enabled`: 예약 스캔 켬/끔. 꺼도 `cron_schedule`은 남는다
- `scan_status`: `ready` / `scanning` / `cancelling` / `failed` / `interrupted` — 전이는 [spec_scanner_queue_state_transitions.md](./spec_scanner_queue_state_transitions.md)
- `pending_delete`: 0 정상, 1 삭제 중, 2 다른 세션으로 이동해 나가는 중, 3 이동해 들어오는 중(대상). `transfer_target_id`는 이동 대상 카테고리 id. 삭제·이동은 스캐너 큐 작업(`library_delete`/`library_transfer`)이 나눠서 처리하며, 목록 쿼리는 `COALESCE(pending_delete, 0)`으로 걸러야 한다
- `gdrive_copy_remote`, `gdrive_view_local_mirror_path`: 구글 링크 카테고리(베타)의 rclone 원격 이름과 메타데이터 로컬 미러 경로
- `hide_cover`: 카테고리 단위로 대표/목록 커버 렌더링을 숨길지 여부를 저장 (`INTEGER DEFAULT 0`)
- `content_kind`: 카테고리 속성 코드(`library_kinds.code`, 논리 참조). 기본값 `'unspecified'`(미지정). 플러그인이 분류 기준(예: 연관작품 검색에서 만화/도서 구분)으로 읽을 수 있다 (`TEXT NOT NULL DEFAULT 'unspecified'`, MariaDB는 `VARCHAR(24)`)
- `hide_title`: 카테고리 단위로 그리드 카드의 제목 텍스트를 숨기고 썸네일만 표시할지 여부 (넷플릭스 스타일). 일반/성인 도서 세션에서만 UI 노출 (`INTEGER DEFAULT 0`)
- `cover_aspect_ratio`: 카테고리 단위 그리드 카드 커버 화면비율. `'4:3'`(기본) 또는 `'16:9'`만 허용 (`TEXT DEFAULT '4:3'`)
- 참고: 운영 DB에는 과거 마이그레이션 잔여 컬럼이 남아 있을 수 있음

### books

도서 메타데이터 및 파일 식별 정보.

- PK: `id`
- 주요 FK: `library_id -> libraries.id`
- 주요 컬럼:
  - 식별/경로: `id`, `library_id`, `file_path`, `file_format`
  - 메타: `title`, `series_name`, `author`, `isbn`, `publisher`, `summary`, `genre`, `tags`, `link`, `release_date`, `score`, `publication_status`, `cover_artist`, `teams`, `locations`, `characters`
  - 콘텐츠 등급: `books_lv` (사용자 `content_rating_max`와 비교)
  - 뷰어/커버: `total_pages`, `cover_image`, `cover_updated_at`, `cover_align`, `has_offsets`
  - 배너: `banner_image`, `banner_updated_at` - 상세 페이지 히어로 이미지용(선택). 표지와 동일한 파일경로 MD5 해시로 `covers/<library_id>/banner_<hash>.webp`에 저장되며, 스캐너가 폴더 내 `banner.<ext>` 파일 또는 메타 YAML의 `banner`(Base64) 필드에서 채운다 - 둘 다 없으면 비워둠(표지처럼 zip/epub 내부를 강제 추출하지 않음)
  - 상태/보호: `metadata_locked`, `created_at`
  - 정렬/별칭: `series_alias`, `title_alias`
  - 운영 확장: `is_deleted`, `deleted_at`, `file_mtime`, `file_size`
- 비고: `is_favorite` 컬럼은 레거시 호환용으로 남아 있으나, 현재 즐겨찾기 실사용 저장소는 `user_favorites`입니다.

### book_offsets

압축 파일(예: ZIP) 내부 페이지 오프셋 캐시. 뷰어가 페이지 하나를 요청할 때마다 zip 전체를 열지 않고, 여기 저장된 offset으로 필요한 바이트 구간만 seek/read 합니다.

- PK: `id`
- 주요 FK: `book_id -> books.id`
- 컬럼: `book_id`, `page_idx`, `filename`, `local_header_offset`, `compress_size`, `file_size`, `compress_type`, `data_offset`
- `data_offset`: 압축 데이터가 실제로 시작하는 위치. 원격(FUSE) 경로는 페이지마다 헤더를 읽으면 원격 요청이 늘어나 스캔 때 계산하지 않고 NULL로 둔다 — 뷰어는 로컬 헤더를 읽어 위치를 구하는 방식으로 대신한다
- MariaDB에서는 offset 관련 컬럼이 `BIGINT`로, 4GB(ZIP64)를 넘는 대용량 원본 아카이브도 지원합니다.

### series_summary / series_summary_state

시리즈 그룹핑·대표 표지 사전 집계 캐시 (라이브러리 목록 렌더링 고속화용).

- `series_summary` PK: (`library_id`, `series_key`) 복합키
  - 컬럼: `representative_book_id`, `series_book_count`, `sort_series_name`, `latest_added`
  - 큐 스캔이 끝나면 전체를 다시 만들고(`SeriesRepository.rebuild_summary`), 큐를 거치지 않는 직접 스캔(경로 지정·웹훅·웹뷰 다운로드)은 바뀐 시리즈 줄만 다시 계산한다(`services/scan_refresh_service.py`의 `track_direct_scan`)
- `series_summary_state` PK: `id`
  - 컬럼: `is_ready`, `refreshed_at` — 백그라운드 재집계 완료 여부 플래그

### audiobooks

오디오북(작품 단위) 메타데이터.

- PK: `id`
- 주요 FK: `library_id -> libraries.id`
- 컬럼: `title`, `sort_title`, `web_id`, `author`, `publisher`, `code`, `poster`, `premiered`, `ratings`, `author_intro`, `description`, `folder_name`, `folder_path`(UNIQUE), `total_duration`, `total_tracks`, `file_type`, `is_favorite`, `metadata_locked`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`

### audiobook_tracks

오디오북 개별 트랙(파일) 정보.

- PK: `id`
- 주요 FK: `audiobook_id -> audiobooks.id` (ON DELETE CASCADE)
- 컬럼: `track_number`, `track_code`, `filename`, `file_path`(UNIQUE), `file_mtime`, `file_size`, `duration`, `format`, `title`, `artist`
- `title`/`artist`: 음악 카테고리(속성 `music`) 곡의 표시용 제목/아티스트(태그, 없으면 파일명). 오디오북 트랙은 NULL

### audiobook_progress / audiobook_track_progress

오디오북 사용자별 재생 진행률(작품 단위 / 트랙 단위).

- `audiobook_progress` 주요 FK: `audiobook_id -> audiobooks.id`, `current_track_id -> audiobook_tracks.id`
  - 컬럼: `user_id`, `current_time`, `total_progress_pct`, `playback_rate`, `is_completed`, `last_listened_at`
  - 제약: `UNIQUE(audiobook_id, user_id)`
- `audiobook_track_progress` 주요 FK: `audiobook_id -> audiobooks.id`, `track_id -> audiobook_tracks.id`
  - 컬럼: `user_id`, `current_time`, `progress_pct`, `is_completed`, `updated_at`
  - 제약: `UNIQUE(audiobook_id, track_id, user_id)`
- `audiobook_music_lookups`: 음악 카테고리 앨범의 외부 정보 조회 결과 (`lookup_music_album` 플러그인 폴백). PK `audiobook_id`
  - 컬럼: `status`(found/not_found/skipped), `source`(플러그인 id), `artist`, `year`, `genres`, `summary`, `cover_url`, `source_url`, `looked_up_at`
  - 스캔이 덮어쓰지 않도록 audiobooks와 따로 두고, 화면에는 빈 칸에만 겹쳐 보인다. 앨범마다 한 번만 조회한다

### users

사용자 계정 및 권한.

- PK: `id`
- 컬럼: `username`(UNIQUE), `password_hash`, `role`, `is_default_password`, `has_adult_access`, `has_audiobook_access`, `has_video_access`, `has_download_access`, `content_rating_max`, `created_at`
- 4개 DB에 같은 `username`으로 복제된다(id는 DB마다 다를 수 있음). 로그인·권한은 general DB 기준
- 오디오북·영상 접근은 실제로 `user_category_permissions`(카테고리별)로 막는다. `has_audiobook_access`/`has_video_access`는 화면 스위치가 없어 사실상 늘 1

### user_progress

도서별 사용자 진행률.

- PK: `id`
- 주요 FK: `book_id -> books.id`, `user_id -> users.id`
- 컬럼: `pages_read`, `is_completed`, `last_read_at`, `last_epub_cfi`, `last_epub_href`, `last_epub_spine_index`, `last_epub_percent`, `last_epub_fingerprint`, `last_epub_updated_at`
- 참고: EPUB은 서버/클라이언트 세션 포인터(예: CFI, href, spine index) 기반 이어읽기에 이 컬럼들을 사용합니다.
- 제약: `UNIQUE(book_id, user_id)`

### user_reading_log

사용자 읽기 활동 로그(일별 집계/통계 근거).

- PK: `id`
- 주요 FK: `book_id -> books.id`, `user_id -> users.id`
- 컬럼: `pages_read_delta`, `duration_seconds`, `read_date`

### user_favorites

사용자별 즐겨찾기 매핑 테이블.

- PK: `id`
- 주요 FK: `user_id -> users.id`, `book_id -> books.id`
- 컬럼: `user_id`, `book_id`, `created_at`
- 제약: `UNIQUE(user_id, book_id)`

### user_category_permissions

사용자-라이브러리 접근 권한 매핑.

- PK: `id`
- 주요 FK: `user_id -> users.id`, `library_id -> libraries.id`
- 컬럼: `has_access`
- 제약: `UNIQUE(user_id, library_id)`

### collections / collection_items

사용자 정의 컬렉션(도서/시리즈/오디오북을 자유롭게 묶는 모음).

- `collections` PK: `id`
  - 주요 FK: `user_id -> users.id`
  - 컬럼: `name`, `description`, `color`, `cover_image`, `created_at`, `updated_at`
- `collection_items` PK: `id`
  - 주요 FK: `collection_id -> collections.id`(CASCADE), `book_id -> books.id`(CASCADE, nullable), `audiobook_id -> audiobooks.id`(CASCADE, nullable), `video_id`(nullable, 영상 DB의 `videos.id`를 논리 참조)
  - 컬럼: `series_name`(nullable), `sort_order`, `created_at`
  - 제약: `UNIQUE(collection_id, book_id)`, `UNIQUE(collection_id, series_name)`, `UNIQUE(collection_id, audiobook_id)` — 도서/시리즈/오디오북/영상 중 하나만 채워짐

### scanner_tasks

백그라운드 스캐너 작업 대기열. 끝난 작업은 `scan_history`로 옮기고 이 표에서 지운다.

- PK: `id`
- 컬럼: `task_type`, `task_key`(UNIQUE), `status`, `kwargs`, `stage`, `worker_pid`, `cancel_requested`, `enqueue_at`, `started_at`, `finished_at`, `error_message`
- 작업 종류·상태 전이·취소: [spec_scanner_queue_state_transitions.md](./spec_scanner_queue_state_transitions.md)

### scan_history

완료된 스캔 작업 이력(스캐너 로그/통계, 알림센터 "최근 완료" 출처).

- PK: `id`
- 컬럼: `task_type`, `task_key`, `status`, `kwargs`, `enqueue_at`, `started_at`, `finished_at`, `error_message`, `result_summary`, `created_at`
- `kwargs.trigger_type`: 스캔 출처 `manual` / `cron` / `lazy` / `webhook` (없으면 예전 행)
- `result_summary`(JSON): 카테고리 스캔 `{"new_books", "errors", "report_file"}`, 선택 도서 스캔 `{"books", "succeeded", "errors"}`. 그 밖의 작업은 NULL
- 보관: 90일 지난 행은 서버 시작 시 정리

### problem_occurrences

알림센터 문제 카드의 발생 기록. **대상 1개 x 코드 1개 = 1행**이며 재발하면 횟수/마지막 시각만 늘어난다(UPSERT).
설계: [plan_unified_notification_queue.md](plan_unified_notification_queue.md).

- PK: `id`, UNIQUE `(code, db_type, target_type, target_id)`
- 대상: `db_type`, `library_id`, `target_path`(파일 경로), `occurrence_count`(재발 횟수)
- `code`: 문제 종류 — 스캐너 `file_missing`/`mass_missing`/`remote_unavailable`/`file_corrupt`/`cover_missing`/`unknown`,
  시스템 `system_task_failed`, 사용자 신고 `user_report`, 플러그인 `<plugin id>:<code>`
- `severity`: `action_required`(빨간 점) / `notice` / `auto_fixed`
- `source`: `scanner` / `system` / `viewer` / `plugin:<plugin id>`
- `target_type` + `target_id`: `book`(book_id) / `series`(`"library_id|series_name"`) / `library`(library_id) / `system`(작업 키, 플러그인은 `-`)
- `series_key`: `"library_id|series_name"` (도서가 지워져도 시리즈별로 묶기 위함, 화면 비노출)
- `group_key`: 카드 키 = `code|db_type|library_id` (플러그인은 `plugin:<id>|<code>|-`)
- `title`/`detail`: 플러그인이 준 문구 (코어 코드는 i18n 키로 표시하므로 비어 있음)
- `message`(원문 오류, 500자), `context`(JSON: 신고자, 플러그인 id/이름/조치 등)
- 시각: `first_seen_ms`, `last_seen_ms`, `resolved_ms` (epoch ms — DB 시간대와 무관)
- `status`: `open` / `resolved`. 해결된 행은 30일 뒤 서버 시작 시 정리. 카테고리 삭제 시 그 카테고리 행 삭제

### problem_groups

카드(group_key) 단위 상태 — "알고 있음"(음소거).

- PK: `group_key`
- 컬럼: `muted_ms`, `muted_count` (음소거할 때의 열린 개수 - 그보다 늘어나면 다시 보인다)
- 열린 행이 없어진 카드의 행은 자동 삭제

### scanner_progress

스캐너의 폴더 단위 진행 상태 기록.

- 복합 키 성격 컬럼: `library_id`, `folder_path`(PK)

### folder_mtimes

폴더 변경 시각 캐시(증분 스캔 최적화).

- 키 성격 컬럼: `folder_path`(PK)
- 컬럼: `dir_mtime`, `meta_mtime`

### settings

전역/플러그인 설정 저장소.

- PK: `key`
- 컬럼: `key`, `value`, `updated_at`
- 주요 키 예시:
  - `TAG_FILTER_SEARCH_SCOPE_ALL`
  - `RCLONE_RC_URL`
- 플러그인 관련 키 예시:
  - `PLUGIN_ENABLED_<plugin_id>`
  - `PLUGIN_CONFIG_<plugin_id>`

### plugin_load_events

플러그인 로드/오류 이벤트 로그.

- PK: `id`
- 컬럼: `plugin_id`, `status`, `message`, `occurred_at`

### plugin_group_assignments

플러그인 카테고리 탭을 사이드바 그룹(`library_groups`)에 넣는 배치.

- PK: `plugin_id`
- 컬럼: `group_id`, `sort_order`

### videos / video_episodes

영상 강좌(폴더 1개 = 강좌)와 회차 파일. 영상 DB에서만 쓴다.

- `videos` PK: `id`, 주요 FK: `library_id -> libraries.id`
  - 컬럼: `title`, `sort_title`, `web_id`, `genres`, `poster`, `backdrop`, `premiered`, `description`, `folder_name`, `folder_path`(UNIQUE), `total_duration`, `total_episodes`, `is_favorite`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`
- `video_episodes` PK: `id`, 주요 FK: `video_id -> videos.id`(CASCADE)
  - 컬럼: `episode_number`, `episode_code`, `title`, `filename`, `file_path`(UNIQUE), `file_mtime`, `file_size`, `duration`, `width`, `height`, `premiered`, `format`, `needs_transcode`, `subtitle_path`, `container_verified`
  - `needs_transcode`: 브라우저가 그대로 못 트는 코덱이면 1(ffmpeg 변환 재생). `duration`/`width`/`height`/`container_verified`는 lazy 스캐너가 ffprobe로 나중에 채운다

### video_progress / video_episode_progress

영상 사용자별 시청 진행률(강좌 단위 / 회차 단위). 오디오북 진행률과 같은 구조다.

- `video_progress` 주요 FK: `video_id -> videos.id`(CASCADE), `current_episode_id -> video_episodes.id`
  - 컬럼: `user_id`, `current_time`, `total_progress_pct`, `playback_rate`, `is_completed`, `last_watched_at`
  - 제약: `UNIQUE(video_id, user_id)`
- `video_episode_progress` 주요 FK: `video_id`, `episode_id`(모두 CASCADE)
  - 컬럼: `user_id`, `current_time`, `progress_pct`, `is_completed`, `updated_at`
  - 제약: `UNIQUE(video_id, episode_id, user_id)`

### user_settings

사용자별 설정(전역 `settings`와 같은 key/value 형태). general DB에만 쓴다.

- PK: `id`, 제약 `UNIQUE(user_id, key)`
- 컬럼: `user_id`, `key`, `value`, `updated_at`

### book_annotations / epub_bookmarks

EPUB/TXT 읽기 중 남긴 형광펜·메모와 책갈피.

- `book_annotations` 주요 FK: `book_id -> books.id`
  - 컬럼: `user_id`, `format`, `chapter_idx`, `start_offset`, `end_offset`, `quote`, `prefix`, `suffix`, `color`, `note`, `plugin_marker`, `created_at`, `updated_at`
  - `quote`/`prefix`/`suffix`: 본문이 조금 바뀌어도 위치를 다시 찾기 위한 앞뒤 문맥. `plugin_marker`: 플러그인이 만든 주석 표시
- `epub_bookmarks` 주요 FK: `book_id -> books.id`
  - 컬럼: `user_id`, `format`, `chapter_idx`, `percent`, `label`, `created_at`

### tts_progress

TTS(읽어 주기) 위치. 듣던 위치와 눈으로 읽던 위치를 따로 둔다.

- PK: `id`, 주요 FK: `book_id -> books.id`, 제약 `UNIQUE(book_id, user_id)`
- 컬럼: `listen_chapter`, `listen_offset`, `listen_text_len`, `listen_anchor`, `listen_updated_ms`, `read_chapter`, `read_offset`, `read_text_len`, `read_anchor`, `read_updated_ms`, `voice`, `steps`, `speed`

### tts_audio_books / tts_audio_pieces / tts_pregen_jobs / tts_audio_cache

서버에서 TTS 음성을 미리 만들어 두는 기능(선택). 음성 파일은 `tts_audio/` 아래 책별 `.pack`에 쌓인다.

- `tts_audio_books`: 책 × 음성 설정 1개 = 1행. 제약 `UNIQUE(book_id, voice, steps, speed, quality)`
  - 컬럼: `book_id`, `voice`, `steps`, `speed`, `quality`, `rel_dir`, `pieces`, `bytes`, `duration_sec`, `created_by`, `created_ms`, `last_used_ms`
- `tts_audio_pieces`: `.pack` 안 조각의 위치. PK `(audio_book_id, piece_key)`
  - 컬럼: `chapter`, `part`, `byte_offset`, `byte_length`, `duration_sec`
- `tts_audio_cache`: v2.7.9의 조각 단위 캐시 색인. 지금은 쓰지 않고 `clear_legacy_cache()`가 비우기만 한다. PK `piece_key`
- `tts_pregen_jobs`: 미리 만들기 작업. `status` 기본 `queued`
  - 컬럼: `book_id`, `user_id`, `voice`, `steps`, `speed`, `quality`, `status`, `total_pieces`, `done_pieces`, `error`, `heartbeat_ms`, `created_ms`, `finished_ms`

### gdrive_book_copies

구글 링크 카테고리(베타)에서 열려고 받아 둔 책 사본의 상태. 오래된 사본은 주기 작업이 지운다.

- PK: `id`, 주요 FK: `book_id -> books.id`(UNIQUE)
- 컬럼: `library_id`, `source_file_id`, `status`(`copied` / `unsupported`), `local_path`, `error_message`, `updated_at`

### kosync_credentials / kosync_documents / kosync_progress

KOReader 진행률 동기화(kosync). general DB에만 쓴다.

- `kosync_credentials`: PK `user_id`, 컬럼 `key_hash`, `updated_at`
- `kosync_documents`: KOReader 문서 해시 → 책. PK `document`, 컬럼 `db_type`, `book_id`, `created_at`
- `kosync_progress`: PK `(user_id, document)`, 컬럼 `progress`, `percentage`, `device`, `device_id`, `timestamp`

### mcp_pending_changes

MCP 쓰기 도구(Tier B)가 바로 적용하지 않고 관리자 승인을 기다리게 둔 변경. general DB에만 쓴다.

- PK: `id`
- 컬럼: `tool_name`, `db_type`, `target`, `payload`(JSON), `preview`, `status`(기본 `pending`), `created_at`, `decided_at`, `decided_by`, `decision_note`

---

## 4. 관계 요약

- `library_groups (1) -> libraries (N)`
- `libraries (1) -> books (N)`
- `libraries (1) -> audiobooks (N)`
- `books (1) -> book_offsets (N)`
- `books (1) -> user_progress (N)`
- `books (1) -> user_reading_log (N)`
- `books (1) -> user_favorites (N)`
- `books (1) -> collection_items (N)`
- `audiobooks (1) -> audiobook_tracks (N)`
- `audiobooks (1) -> audiobook_progress (N)`
- `audiobooks (1) -> audiobook_track_progress (N)`
- `audiobooks (1) -> collection_items (N)`
- `audiobook_tracks (1) -> audiobook_track_progress (N)`
- `users (1) -> user_progress (N)`
- `users (1) -> user_reading_log (N)`
- `users (1) -> user_favorites (N)`
- `users (1) -> user_category_permissions (N)`
- `users (1) -> collections (N)`
- `users (1) -> audiobook_progress (N)`
- `libraries (1) -> user_category_permissions (N)`
- `collections (1) -> collection_items (N)`
- `libraries (1) -> videos (N)`, `videos (1) -> video_episodes (N)`, `videos (1) -> video_progress / video_episode_progress (N)`
- `books (1) -> book_annotations / epub_bookmarks / tts_progress (N)`
- `books (1) -> tts_audio_books (N)`, `tts_audio_books (1) -> tts_audio_pieces (N)`
- `books (1) -> gdrive_book_copies (0..1)`, `books (1) -> kosync_documents (N)`

**책에 딸린 테이블을 새로 만들면** 다음 세 곳의 정리 목록에도 넣어야 합니다. 빠뜨리면 카테고리 삭제·이동, 휴지통 비우기 때 그 행이 남습니다.
- `repositories/category_data_shared.py`의 `purge_book_dependents` (카테고리 삭제·이동)
- `repositories/trash_repository_shared.py` (휴지통 영구 삭제)
- `tools/scanner/sync_detector.py`의 7일 자동 비우기

---

## 5. 플러그인 개발 시 DB 사용 원칙

- 직접 `import database`/`database.get_connection(...)` 대신 BaseProvider 헬퍼 사용
  - `self.get_db_gateway(db_type)`
  - `self.get_plugin_config(db_type, default={})`
- 설정 저장은 `settings` 테이블의 플러그인 키 규칙을 사용
- SQLite/MariaDB 간, 그리고 DB 간 컬럼 편차가 있을 수 있으므로, 신규 쿼리는 두 엔진 호환성을 고려해 작성 (예: `INTEGER` vs `BIGINT`, upsert 문법 차이 등)

---

## 6. 스키마 원본 (컬럼 타입·인덱스)

컬럼 타입, 기본값, 인덱스는 이 문서에 옮겨 적지 않습니다(예전 사본은 금방 낡았습니다). 아래 원본을 직접 보세요.

- SQLite: `services/db_migration_service.py` — `_SCHEMA_SQL`(테이블), `_INDEXES_SQL`(인덱스)
- MariaDB: `services/schema_mariadb.py` — `MARIADB_CENTRAL_SCHEMA`(테이블), 운영 DB 보강용 컬럼·인덱스 목록은 `services/db_migration_service.py`
- 컬럼을 추가하는 절차(두 원본을 함께 고치기, 보강 목록에 넣기): [change_db_guide.md](./change_db_guide.md)

---

## 7. 스캔 대상 파일과 실제 데이터 흐름 요약

- **로컬 파일**: 스캐너가 파일을 직접 열어 메타데이터/커버/오프셋을 추출 후 위 테이블에 저장.
- **원격 파일(rclone/Google Drive 마운트 등)**: `libraries.is_remote=1`인 라이브러리는 스캔 시 무거운 I/O(커버 추출 등)를 지연시키고, `book_offsets`만 우선 채워 뷰어 스트리밍(seek 기반 부분 읽기)을 즉시 가능하게 합니다. 자세한 내용은 [spec_scanner_logic.md](./spec_scanner_logic.md), [spec_feature_overview.md](./spec_feature_overview.md) 참고.
