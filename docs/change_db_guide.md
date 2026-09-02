# DB 스키마/마이그레이션 코드 변경 가이드

작성일: 2026-09-02. **DB 스키마를 조금이라도 건드리기 전에 이 문서부터 읽을 것.**
새 인스턴스(다음 세션/다른 작업자)가 예전 구조를 기억 못 하고 똑같은 실수(마이그레이션
로직을 또 두 군데에 나눠 만드는 것)를 반복하지 않게 하기 위한 문서다.

## 배경 (왜 이런 구조가 됐는가)

예전엔 "부족한 컬럼/인덱스 생성 + 백필" 로직이 `database.py`(커넥션 풀링과 함께)와
`tools/db_schema_updater.py`(MariaDB 전용 수작업 리스트)에 각각 따로 있었다. 두 배포
경로(`entrypoint.sh`/`manage.sh`) 모두 `db_schema_updater.py`를 서브프로세스로 먼저
실행한 뒤, `core.py` 임포트 시 `database.py`의 `init_databases()`가 프로세스 내에서
또 한 번 실행되는 구조였는데, SQLite는 위임 관계라 괜찮았지만 **MariaDB는 완전히
별개의 두 메커니즘이 독립적으로 존재해 새 컬럼을 추가할 때마다 두 곳에 손으로
반영해야 했다.** 실제로 이 때문에 실제 버그가 있었다: `_backfill_audiobook_last_listened_at`의
MariaDB 제로데이트(`0000-00-00 00:00:00`) 처리가 `db_schema_updater.py`에만 있고
`database.py`에는 없었다. `db_schema_updater.py` 자체 주석에도 "database.py 리팩터링
때 이 커플링이 조용히 한 번 깨진 적 있다"는 회귀 이력이 남아있었다.

2026-09-02 세션에서 이 마이그레이션 레이어를 하나로 통합했다 (아래 구조). **초기 테이블
생성 DDL 자체(SQLite `_SCHEMA_SQL` vs MariaDB `MARIADB_CENTRAL_SCHEMA`)는 의도적으로
지금도 별도로 유지한다** — 다이얼렉트 변환 계층까지 통합하는 건 별개의, 훨씬 위험한
작업이라 범위 밖으로 뒀다.

## 지금 구조 (3개 파일, 역할 고정)

| 파일 | 역할 | 건드릴 일 |
|---|---|---|
| `database.py` | 커넥션 풀링(SQLite/MariaDB)만. `init_databases()`는 `run_full_migration()`을 호출하는 얇은 래퍼 | 풀링 관련 변경일 때만 |
| `services/db_migration_service.py` | **컬럼/인덱스 diff + 백필의 유일한 소스.** `_SCHEMA_SQL`(SQLite DDL), `_INDEXES_SQL`, `auto_migrate_schema`, MariaDB 전용 안전망(`_ensure_mariadb_columns`/`_ensure_mariadb_indexes`), 모든 백필 함수, 오케스트레이터 `run_full_migration()` | **스키마를 바꿀 때 여기만 고치면 됨** |
| `tools/db_schema_updater.py` | 얇은 CLI 진입점. MariaDB `MARIADB_CENTRAL_SCHEMA`(초기 테이블 생성 DDL, `_SCHEMA_SQL`과 별개)와 SQLite WAL 체크포인트만 자체 로직으로 갖고, 나머지는 `run_full_migration()` 호출 | MariaDB 초기 생성 DDL을 바꿀 때만 |

`database.init_databases()`와 `tools/db_schema_updater.py`의 `run_schema_update()`
**둘 다 결국 `services/db_migration_service.py`의 `run_full_migration()` 하나만
호출한다.** 이게 핵심 불변 조건이다 — 이걸 깨고 한쪽에만 로직을 추가하면 예전과
같은 버그가 재발한다.

## 새 컬럼/인덱스를 추가할 때 (제일 흔한 케이스)

1. `services/db_migration_service.py`의 `_SCHEMA_SQL`(컬럼) 또는 `_INDEXES_SQL`(인덱스)에
   SQLite 방언으로 추가한다. **이것만으로 SQLite와 MariaDB 둘 다 자동으로 컬럼이
   생긴다** — `auto_migrate_schema()`가 두 엔진 모두에 대해 이 텍스트를 diff-parse해서
   `ALTER TABLE`을 실행하기 때문 (MariaDB도 `SHOW COLUMNS`로 실존 컬럼을 조회해서 비교함).
2. **MariaDB 전용 다이얼렉트 문제가 있는 컬럼**(예: `CHARACTER SET`/`COLLATE` 지정이
   필요하거나, `auto_migrate_schema`의 범용 로직이 신뢰할 수 없다고 판단되는 경우)만
   추가로 `_ensure_mariadb_columns()`/`_ensure_mariadb_indexes()`의 튜플 리스트에도
   넣는다. **이건 "안전망"이지 필수 단계가 아니다** — 대부분의 컬럼 추가는 1번만으로
   충분하다.
3. 완전히 새 테이블을 만드는 경우에만 `tools/db_schema_updater.py`의
   `MARIADB_CENTRAL_SCHEMA`에도 MariaDB 방언으로 `CREATE TABLE`을 추가해야 한다
   (초기 생성은 통합 안 돼 있으므로 여기는 여전히 손으로 동기화 필요 — 유일하게
   남은 "두 곳 동기화" 지점이니 새 테이블 추가 시에는 반드시 둘 다 확인할 것).

## 하지 말 것 (불필요한 수정 방지)

- **`database.py`에 마이그레이션/백필 함수를 다시 추가하지 말 것.** 커넥션 풀링
  전담 파일로 되돌리는 게 이번 정리의 목적이었다.
- **`tools/db_schema_updater.py`에 컬럼/인덱스 diff나 백필 로직을 다시 추가하지 말 것.**
  `MARIADB_CENTRAL_SCHEMA`(초기 생성 DDL)와 WAL 체크포인트 외엔 전부
  `services/db_migration_service.py`로 가야 한다.
- **`_SCHEMA_SQL`/`_INDEXES_SQL`과 `MARIADB_CENTRAL_SCHEMA`를 하나로 합치려 하지
  말 것.** 사용자와 합의하고 의도적으로 남겨둔 스코프 밖 영역이다 (다이얼렉트
  변환 계층이 필요해 리스크가 훨씬 큼). 정말 필요하다고 판단되면 먼저 사용자와
  상의할 것.
- **`services/db_migration_service.py` 최상단에 `import database`를 추가하지 말 것.**
  `database.py`가 파일 하단에서 이 모듈의 `run_full_migration`을 다시 import하는
  구조라, 이 모듈이 (database.py를 거치지 않고) 최초 진입점으로 직접 import되면
  순환 참조로 깨진다 (2026-09-02에 실제로 재현/수정한 버그). `database`가 필요한
  함수 안에서 **그 함수 본문 맨 위에 지역 import**로만 써야 한다. 이미 그렇게
  돼 있는 기존 함수들(`startup_db_sanity_check`, `_connect_and_init_schema`,
  `_seed_settings_and_admin`, `run_full_migration`)을 그대로 패턴으로 따라할 것.

## 검증 방법 (스키마 변경 후 반드시 실행)

1. `.venv/Scripts/python -c "import database; import services.db_migration_service; import tools.db_schema_updater"` —
   순환 임포트 없이 되는지. **`from services.db_migration_service import run_full_migration`을
   database를 거치지 않고 최초 진입점으로 직접 실행해도** 깨지지 않는지 별도로 확인할 것
   (`.venv/Scripts/python -c "from services.db_migration_service import run_full_migration"`).
2. 임시 디렉토리로 `database.DB_GENERAL_PATH` 등을 갈아끼운 뒤 `database.init_databases()`를
   직접 호출해 SQLite 경로가 정상 동작하는지 확인 (테이블 생성, admin 시딩 등).
3. **가능하면 Docker로 SQLite/MariaDB 둘 다 신선한 컨테이너로 실측한다** — 이번 세션에서
   쓴 방법: `docker-compose.build.yml`/`docker-compose.mariadb.yml` 패턴을 참고해 격리된
   테스트용 compose 파일(다른 포트/컨테이너 이름/볼륨 경로)을 만들어 `docker compose up
   -d --build`로 띄우고, `docker logs <container>`에서 "1단계"(마이그레이션)와 "2단계"
   (SQLite는 WAL 체크포인트, MariaDB는 컬럼/인덱스 안전망) 로그가 에러 없이 끝까지
   나오는지, 그리고 실제로 `/login`에 admin/admin으로 로그인되는지까지 확인한다.
   MariaDB는 `docker-compose.mariadb.yml`의 `mariadb`/`mariadb-grant-repair` 서비스
   정의를 그대로 재사용하면 된다 (이미지: `mariadb:10.11`).
4. 확인 후 테스트용 컨테이너/볼륨은 정리한다 (실제 배포 컨테이너와 이름이 겹치지
   않게 하고, 확인 끝나면 `docker compose down`).

## 관련 기록

- 2026-09-02 통합 작업의 전체 조사/설계 과정은 그 세션의 대화 기록(플랜 파일)에
  더 자세히 남아있음 — 이 문서는 "다음에 뭘 해야/하지 말아야 하는지"만 담은
  실용 가이드고, "왜 이렇게 됐는지"의 세부 조사 근거(정확한 원본 줄 번호, git
  커밋 등)는 다루지 않는다.
