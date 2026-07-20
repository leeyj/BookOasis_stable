# DB 고도화 및 쿼리 분리 리팩토링 상세 가이드 (Roadmap)

이 문서는 BookOasis가 SQLite 단일 내장 DB 체제에서 향후 **PostgreSQL 및 MariaDB(MySQL) 이중 지원 구조**로 도약하기 위해, 프로젝트 전반에 산재한 raw SQL 쿼리를 **리포지토리 패턴(Repository Pattern)**으로 점진적 분리하기 위한 이행 가이드라인입니다. 

다음 세션의 AI 어시스턴트는 이 문서를 정독하고 지목된 파일들을 순서대로 리팩토링해 나가면 됩니다.

---

## 🎯 1. 리팩토링 목표 및 배경

현재 프로젝트는 SQLite의 가볍고 편리함을 잘 살려 배포 중이나, 대규모 도서 인덱싱(수만 권 이상) 환경에서 메인 스캔과 레이지 스캔이 동시에 작동할 때 **파일 수준의 쓰기 락 경합(`database is locked`) 및 WAL 손상 위험**이 존재합니다.
이를 근본적으로 극복하기 위해 다중 RDBMS 지원을 준비해야 하며, 그 1단계 선제 조건은 **"비즈니스 로직(Flask, Services)과 물리 쿼리(Raw SQL)의 완벽한 결별"**입니다.

### 핵심 설계 원칙
1. **완벽한 캡슐화**: 비즈니스 서비스나 API 핸들러(`services/`, `api/`) 내에서 직접 `database.get_connection()`을 호출하고 raw SQL 문자열을 실행하던 하드코딩을 전면 금지하고, 무조건 `repositories/` 하위 모듈을 경유하도록 합니다.
2. **다중 DB 방언 대응 (Dialect Independence)**:
   - **플레이스홀더 자동 대치**: SQLite는 `?`, PostgreSQL은 `$1`, MariaDB는 `%s`를 씁니다. 리포지토리 실행 단계에서 현재 활성 커넥션 타입에 맞추어 플레이스홀더를 매핑해주는 어댑터 함수를 경유하도록 설계합니다.
   - **신규 행 ID 획득 이원화**: SQLite/MariaDB의 `cursor.lastrowid`와 PostgreSQL의 `INSERT ... RETURNING id` 문법 차이를 해결할 수 있도록 쓰기 레포지토리 메서드는 다형성 분기를 제공해야 합니다.

---

## 📂 2. 리팩토링 대상 파일 및 수정 가이드

가장 핵심적이고 쿼리가 밀집된 파일들 위주로 우선순위를 지정하여 정리합니다.

### 📍 [우선순위 1] 도서 및 시리즈 조회 서비스
도서 목록 검색, 그리드 렌더링, 시리즈 연독 뷰 등 사용자 화면 노출 빈도가 가장 높은 핵심 영역입니다.

#### 1) `services/library_service.py` ➔ `repositories/book_repository.py` 로 이전
* **현재 문제**: `library_service.py` 내부의 `get_books_by_library`, `search_books` 등의 메서드에 대량의 복잡한 SQL 및 동적 필터링 문자열 조립이 하드코딩되어 있습니다.
* **이행 사항**:
  - [NEW] `repositories/book_repository.py` 생성.
  - `BookRepository.get_books_by_library(db_type, ...)` 메서드로 모든 책 조회용 raw SQL을 이전.
  - `BookRepository.search_books_fts(db_type, query, ...)` 메서드로 FTS5 기반 책 검색 쿼리를 이전.

#### 2) `services/series_service.py` ➔ `repositories/series_repository.py` 로 이전
* **현재 문제**: `get_series_detail`, `get_series_recent_list` 등 시리즈 집계 및 연독 관련 쿼리가 직접 삽입되어 있습니다.
* **이행 사항**:
  - [NEW] `repositories/series_repository.py` 생성.
  - `SeriesRepository` 클래스 내부에 시리즈 관련 집계 및 SQL 일체 격리 수용.

---

### 📍 [우선순위 2] OPDS 피드 서비스 및 독서 통계
외부 뷰어(Tachiyomi, KyBook 등) 연동을 위한 피드 생성 레이어와 사용자의 읽기 진행률 기록 레이어입니다.

#### 1) `services/opds_service.py` & `services/opds_compat_service.py`
* **현재 문제**: 외부 기기 대응용 XML 피드를 동적으로 구성하기 위해 `SELECT` 쿼리들이 여러 곳에 인라인으로 박혀 있습니다.
* **이행 사항**:
  - 피드 조회에 필요한 쿼리들을 `BookRepository.get_opds_recent()`, `BookRepository.get_opds_favorites()` 등의 인터페이스로 정립하여 리포지토리로 이전.

#### 2) `services/reading_history_service.py`
* **현재 문제**: 책을 읽을 때마다 진행률을 업데이트하는 `UPDATE user_progress`, `INSERT INTO user_reading_log` 쿼리가 인라인 처리되어 있습니다.
* **이행 사항**:
  - [NEW] `repositories/reading_progress_repository.py` 생성.
  - `ReadingProgressRepository.update_progress(db_type, user_id, book_id, ...)` 로 데이터 액세스 전담.

---

### 📍 [우선순위 3] 백그라운드 큐 및 스캐너 코어
파일 변경을 감지하고 DB에 벌크 삽입/삭제를 수행하는 고성능 일괄 처리 엔진 영역입니다.

#### 1) `services/scanner_queue.py` & `tools/scanner/engine.py`
* **현재 문제**: `ScannerQueue` 및 `_scan_library_internal` 내에서 벌크 인서트(`bulk_insert_books`), 무결성 정돈 등의 SQL이 raw 트랜잭션과 수동으로 복잡하게 얽혀 있습니다.
* **이행 사항**:
  - `repositories/` 하위에 스캐너가 사용하는 DB 배치 쓰기 연산들(`bulk_update_books`, `bulk_insert_books` 등)을 리포지토리 레이어 또는 별도의 `DBWriter` 레포지토리 모듈로 명확하게 일원화.

---

## 🏃‍♂️ 3. SQLite to PostgreSQL 데이터 이관 툴 (Migration Tool) 설계 사양

사용자가 기존 SQLite 기반 데이터를 유실 없이 그대로 PostgreSQL로 옮길 수 있는 마이그레이션 툴(`tools/db_migrator_sqlite_to_pg.py`)의 구현 규격입니다.

### 1) 기술적 이관 핵심 고려 사항
* **외래 키(FK) 제약 준수**: 
  - 데이터 주입 시 외래 키 관계를 준수하여 순차 삽입해야 합니다.
  - 이관 순서: `users` ➔ `libraries` ➔ `books` ➔ `book_offsets` / `user_progress` / `user_reading_log` / `folder_mtimes` / `scanner_progress` / `settings`
* **데이터 타입 변환**:
  - SQLite의 `0` / `1` 정수형 플래그 ➔ PostgreSQL의 `BOOLEAN` (`TRUE`/`FALSE`)으로 형 변환.
  - SQLite의 날짜 텍스트(예: `2026-07-20 14:00:00`) ➔ PostgreSQL의 `TIMESTAMP` 포맷팅 정제.
* **FTS5 가상 테이블 예외 처리**:
  - SQLite의 `books_search` (FTS5) 가상 테이블은 Postgres FTS GIN 인덱싱으로 대체되므로 데이터 물리 복사 대상에서 제외하고, 이관 완료 후 Postgres 측 가상 인덱스를 재빌드하도록 조치합니다.
* **벌크 고속 데이터 주입**:
  - 한 행씩 `INSERT` 시 수십만 권 기준 몇 시간이 소요되므로, `psycopg2` 드라이버의 `execute_values()` 또는 `copy_expert()`를 사용하여 2,000건 단위 벌크 삽입을 가동합니다.

---

## 🏃‍♂️ 4. 다음 AI 어시스턴트를 위한 이행 액션 플랜 (Next Step)

이 문서를 읽은 다음 인스턴스는 아래 순서로 코드를 이어서 작성하십시오.

1. **`repositories/book_repository.py` 신규 생성**:
   * `class BookRepository:` 정적 메서드로 `get_book_by_id`, `get_books_by_library`, `search_books` 등의 인터페이스를 구현하고, [services/library_service.py](file:///c:/project/media_server/services/library_service.py)에 인라인으로 기재된 SQL 구문들을 이동시킵니다.
2. **`services/library_service.py` 리팩토링**:
   * 직접 DB 커넥션을 맺고 쿼리하던 코드를 걷어내고, `BookRepository`를 호출하는 비즈니스 컨트롤러 형태로 전환합니다.
3. **`repositories/series_repository.py` 신규 생성**:
   * `class SeriesRepository:` 정적 메서드로 [services/series_service.py](file:///c:/project/media_server/services/series_service.py)에 있는 시리즈 조인 SQL을 이관합니다.
4. **`tools/db_migrator_sqlite_to_pg.py` 설계 및 구현**:
   * SQLite 파일 경로와 PG 커넥션 URL을 매개변수로 받아 데이터 이관을 원클릭으로 집행하는 마이그레이터 구현.
5. **구문 검사 및 배포 테스트**:
   * `python -m py_compile`을 통한 문법 검사 후 `python deploy.py`를 수행하여 정상 조회가 유지되는지 크로스 검증합니다.
