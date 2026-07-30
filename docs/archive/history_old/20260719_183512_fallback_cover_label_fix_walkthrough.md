---
title: Walkthrough - fallback_cover_label_fix
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

### 스캐너 엔진 구문 오류 조치 완료
- `tools/scanner/engine.py` 파일의 들여쓰기 오류(`IndentationError`)를 정상 수준으로 수선하였습니다.
- 수정 사항 반영 후 `deploy.py`를 통해 원격 운영 서버에 배포 완료하였으며, 웹 서비스와 워커 데몬이 정상 기동(health 체크 정상 통과)함을 E2E로 최종 검증하였습니다.

### 대체 커버(fallback SVG) 라벨 버그 해결
- 프론트엔드가 `/covers/fallback?format=comic`으로 요청할 때, 백엔드 `_format_cover_label`에서 `'comic'` 포맷 문자열이 들어오는 경우에도 정상적으로 `'COMIC'` 상수를 판별해내어 UI 상에 "TEXT"로 오인 매핑되지 않도록 버그를 최종 수정하였습니다.

### 원격 운영 서버 Database 복구 완료
- 배포 이후 발생한 `sqlite3.DatabaseError: database disk image is malformed` 오류에 대해 운영 서버의 `tools/db_recovery.py --yes` 스크립트를 원격 실행하여 정합성을 정상 복구(general/adult DB 모두 ✅ OK 통과)하였고, 서비스를 안전하게 무중단 재구동 완료하였습니다.


