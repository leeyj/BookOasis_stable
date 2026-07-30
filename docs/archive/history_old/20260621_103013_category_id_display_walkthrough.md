---
title: Walkthrough - category_id_display
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 🏁 데이터베이스 레거시 마이그레이션 코드 정리 완료 보고 (Walkthrough)

데이터베이스 파일([database.py](file:///c:/project/media_server/database.py)) 내부에 존재하던 더 이상 작동할 필요가 없는 구형 레거시 컬럼 추가 로직을 안정적으로 걷어내고, 런타임 선언된 스키마 문자열과 실제 데이터베이스의 컬럼들을 대조하여 자동으로 마이그레이션을 수행하는 **동적 스키마 자동 마이그레이터**를 구축했습니다.

## 🛠️ 작업 내용

### 1. 구형 수동 ALTER TABLE 구문 제거 및 동적 스키마 마이그레이션 도입
- **대상 파일**: [database.py](file:///c:/project/media_server/database.py)
- **제거 내용**: `books` 및 `libraries` 테이블의 옛 마이그레이션 대상이었던 `author`, `is_favorite`, `has_offsets`, `cover_updated_at` 등의 컬럼을 추가 시도하는 불필요한 예외 처리 구문(약 55라인)을 완전히 들어냈습니다.
- **도입 내용**: 
  - `parse_schema_columns`: 스키마 정의 문자열 내 테이블과 컬럼 정의를 정규식으로 파싱하여 매핑 딕셔너리로 추출합니다.
  - `auto_migrate_schema`: 파싱한 스키마 정의와 실제 SQLite DB의 `PRAGMA table_info` 정보를 런타임에 대조하여, 결손된 컬럼이 있을 경우 자동으로 `ALTER TABLE ADD COLUMN`을 수행합니다.
- **안정성 조치**: 
  - **SQLite ALTER TABLE non-constant DEFAULT 제약 우회**: SQLite `ALTER TABLE ADD COLUMN` 명령어 실행 시 `DEFAULT CURRENT_TIMESTAMP`와 같은 동적 기본값 지정 시 발생하는 오류(`Cannot add a column with non-constant default`)를 방지하기 위해, 정규식(`DEFAULT\s+(CURRENT_TIMESTAMP|CURRENT_DATE|CURRENT_TIME)`)을 이용하여 동적 기본값 구문을 안전하게 제거한 뒤 컬럼을 추가하도록 구현했습니다.
  - 신규 설치 환경의 경우 최신 `schema` 선언 쿼리 내에 모든 컬럼들이 기본적으로 명시되어 있으므로 빌드 시 즉각 생성됩니다.
  - 이번에 일반 환경설정 관련해서 신규 추가된 `SCANNER_WRITE_LOG` 초기화 매트릭스(`'1'`)와 `libraries` 신규 컬럼 복원 조치는 건드리지 않고 **철저히 보존**하여 호환성을 확보했습니다.

## 🧪 검증 결과 (로컬)
- **동적 마이그레이션 테스트**: 
  - 스키마 내에 `test_column TEXT` 임시 컬럼을 인위적으로 주입한 후 `python database.py`를 실행하여 `[DB-Migration] 동적 스키마 컬럼 추가 완료: libraries.test_column (TEXT)` 로그와 함께 동적으로 ALTER TABLE이 동작함을 확인했습니다.
  - 기존에 존재하던 `cover_updated_at` (DATETIME DEFAULT CURRENT_TIMESTAMP) 등 non-constant 기본값이 설정된 컬럼에 대해서도 예외 처리 우회를 통해 에러 없이 동적 추가가 정상 가동됨을 검증했습니다 (`[DB-Migration] 동적 스키마 컬럼 추가 완료: books.cover_updated_at (DATETIME)`).
- **최종 검증**: `python database.py`가 `Databases initialized successfully.` 결과와 함께 아무런 쿼리 경고나 OperationalError 누출 없이 말끔하게 DB 초기화 및 마이그레이션을 완료하는 것을 확인했습니다.
- **배포 제한 준수**: 홈 서버 스캔 작업에 영향이 가지 않도록 **원격 배포(`deploy.py` 등)는 전혀 수행하지 않고**, 오직 로컬 환경 검증만 무결하게 수행했습니다.
