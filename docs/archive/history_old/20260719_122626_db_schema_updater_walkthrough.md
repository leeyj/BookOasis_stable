---
title: Walkthrough - db_schema_updater
project: BookOasis
category: history
date: 2026-07-19
type: walkthrough
---
# DB 스키마 강제 업데이트 및 동기화 도구 작업 결과 (Walkthrough)

버전 업그레이드 시 DB 변경사항(신규 컬럼, 테이블, 인덱스 등)이 제대로 반영되지 않는 현상을 조치하기 위해 수동 스키마 업데이트 도구를 성공적으로 구축하고 검증하였습니다.

## 변경 사항 (Changes Made)

### [Tools]

#### [NEW] [db_schema_updater.py](file:///c:/project/media_server/tools/db_schema_updater.py)
- `database.py`에서 DB 초기화 모듈을 가져와 수행.
- 테이블 정의 및 누락된 컬럼, 인덱스, FTS5 검색 인덱스를 개별 DB(일반 및 성인)별로 스캔하여 안전하게 추가 및 재구성.
- DB 정합성을 완벽하게 맞추기 위해 `wal_checkpoint(TRUNCATE)`를 강제 수행하여 WAL 임시 데이터 병합.

---

## 검증 결과 (Verification Results)

### 수동 실행 테스트 완료
- `.venv\Scripts\python.exe tools\db_schema_updater.py` 명령을 실행하여 정상 동작함을 확인하였습니다.
- **수행 로그 기록**:
  - `media_general.db` 및 `media_adult.db`의 무결성 검증 통과 (`integrity_check 결과: ok`).
  - 누락된 스키마 컬럼 및 인덱스 확인 완료.
  - WAL 체크포인트를 성공적으로 완료하여 병합 완료.
