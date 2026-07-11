# 🗄️ 데이터베이스 스키마 명세 (SQLite)

BookOasis는 SQLite 기반으로 `general`, `adult` 두 DB 파일을 사용합니다.

- 일반 DB: `db/media_general.db`
- 성인 DB: `db/media_adult.db`

이 문서는 현재 운영 스키마 스냅샷(2026-07-09 기준)과 테이블 역할을 정리합니다.

---

## 1. 스키마 개요

- 두 DB 모두 핵심 테이블은 동일한 구조를 공유합니다.
- 일부 컬럼은 마이그레이션 진행 시점에 따라 DB 간 편차가 있을 수 있습니다.
- 코어/플러그인에서는 컬럼 존재를 가정하기보다, 필요한 경우 안전한 기본값/호환 처리를 권장합니다.

---

## 2. 공통 테이블 목록

두 DB 공통 테이블 (10개):

1. `books`
2. `book_offsets`
3. `libraries`
4. `settings`
5. `users`
6. `user_progress`
7. `user_reading_log`
8. `user_category_permissions`
9. `scanner_progress`
10. `folder_mtimes`

---

## 3. 테이블 상세

### books

도서 메타데이터 및 파일 식별 정보.

- PK: `id`
- 주요 FK: `library_id -> libraries.id`
- 주요 컬럼:
  - 식별/경로: `id`, `library_id`, `file_path`, `file_format`
  - 메타: `title`, `author`, `publisher`, `series_name`, `summary`, `genre`, `tags`, `link`, `release_date`, `score`
  - 뷰어/커버: `total_pages`, `cover_image`, `cover_updated_at`, `has_offsets`
  - 상태: `is_favorite`, `created_at`
  - 일반 DB 확장: `is_deleted`, `deleted_at`, `file_mtime`, `file_size`

### book_offsets

압축 파일(예: ZIP) 내부 페이지 오프셋 캐시.

- PK: `id`
- 주요 FK: `book_id -> books.id`
- 컬럼: `book_id`, `page_idx`, `filename`, `local_header_offset`, `compress_size`, `file_size`, `compress_type`

### libraries

라이브러리 루트 및 스캔 설정.

- PK: `id`
- 컬럼: `name`, `physical_path`, `cron_schedule`, `last_scanned_at`, `scan_status`, `is_remote`, `vfs_refresh_before_scan`, `rclone_rc_url`, `icon`, `color`
- 참고: `media_adult.db`에는 과거 마이그레이션 잔여 컬럼 `test_column`이 존재할 수 있음

### settings

전역/플러그인 설정 저장소.

- PK: `key`
- 컬럼: `key`, `value`, `updated_at`
- 플러그인 관련 키 예시:
  - `PLUGIN_ENABLED_<plugin_id>`
  - `PLUGIN_CONFIG_<plugin_id>`

### users

사용자 계정 및 권한.

- PK: `id`
- 컬럼: `username`, `password_hash`, `role`, `is_default_password`, `created_at`, `has_adult_access`

### user_progress

도서별 사용자 진행률.

- PK: `id`
- 주요 FK: `book_id -> books.id`, `user_id -> users.id`
- 공통 컬럼: `pages_read`, `is_completed`, `last_read_at`
- 일반 DB 확장 (레거시/미사용):
  - `last_epub_cfi`, `last_epub_href`, `last_epub_spine_index`, `last_epub_percent`, `last_epub_updated_at` (구형 epub.js 엔진 관련 필드이며, 통합 텍스트 뷰어 도입으로 더 이상 사용되지 않음)

### user_reading_log

사용자 읽기 활동 로그(일별 집계/통계 근거).

- PK: `id`
- 주요 FK: `book_id -> books.id`, `user_id -> users.id`
- 컬럼: `pages_read_delta`, `duration_seconds`, `read_date`

### user_category_permissions

사용자-라이브러리 접근 권한 매핑.

- PK: `id`
- 주요 FK: `user_id -> users.id`, `library_id -> libraries.id`
- 컬럼: `has_access`

### scanner_progress

스캐너의 폴더 단위 진행 상태 기록.

- 복합 키 성격 컬럼: `library_id`, `folder_path`

### folder_mtimes

폴더 변경 시각 캐시(증분 스캔 최적화).

- 키 성격 컬럼: `folder_path`
- 컬럼: `dir_mtime`, `meta_mtime`

---

## 4. 관계 요약

- `libraries (1) -> books (N)`
- `books (1) -> book_offsets (N)`
- `users (1) -> user_progress (N)`
- `books (1) -> user_progress (N)`
- `users (1) -> user_reading_log (N)`
- `books (1) -> user_reading_log (N)`
- `users (1) -> user_category_permissions (N)`
- `libraries (1) -> user_category_permissions (N)`

---

## 5. 플러그인 개발 시 DB 사용 원칙

- 직접 `import database`/`database.get_connection(...)` 대신 BaseProvider 헬퍼 사용
  - `self.get_db_gateway(db_type)`
  - `self.get_plugin_config(db_type, default={})`
- 설정 저장은 `settings` 테이블의 플러그인 키 규칙을 사용
- DB 간 컬럼 편차가 있을 수 있으므로, 신규 쿼리는 호환성을 고려해 작성
