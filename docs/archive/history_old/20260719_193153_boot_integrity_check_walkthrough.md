---
title: Walkthrough - boot_integrity_check
project: BookOasis
category: history
date: 2026-07-19
type: walkthrough
---
# 서비스 기동 전 DB 무결성 선제 검사 및 자동 복구/스키마 업데이트 의무화 결과 (Walkthrough)

이전 자가 치유(와치독) 기획을 완전히 파기하고, 서비스 기동(시작/재구동) 시점에 데이터베이스 파일 손상(`malformed`) 여부를 선제 체크하여 손상 감지 시 즉시 복구를 진행하며, 안전이 확보된 상태에서 최신 스키마를 동기화한 뒤 기동하도록 보장하는 안전 부팅 체계를 구축하고 배포 완료하였습니다.

## 변경 사항 (Changes Made)

### [Server Controls & Containers]

#### [MODIFY] [manage.sh](file:///c:/project/media_server/manage.sh)
- `start()` 함수 내부 시작부:
  - `media_general.db` 및 `media_adult.db` 파일의 손상이 감지되면 즉시 `python3 tools/db_recovery.py --yes`를 가동하여 정밀 복구 처리 시도.
  - 복구 실패 시 안전을 위해 프로세스 구동을 차단하고 1 코드로 비정상 퇴출.
  - 무결성 검증 통과 후 `python3 tools/db_schema_updater.py`를 호출하여 최신 스키마 컬럼 및 인덱스 정비를 의무 보장.

#### [MODIFY] [entrypoint.sh](file:///c:/project/media_server/entrypoint.sh)
- 도커 기동 시(gosu/root 기동 직전) 동일한 DB 무결성 체크 및 복구/최신 스키마 동기화 의무 가드 삽입.

---

## 검증 결과 (Verification Results)

### 배포 테스트 및 기동 확인 완료
- `deploy.py`를 실행하여 개선된 로직과 안전 장치가 원격 운영 서버에 무결하게 배포 및 동기화 완료되었음을 확인했습니다.
- 원격지 기동 로그 결과:
  - `기동 전 데이터베이스 무결성(PRAGMA integrity_check) 검사` 통과.
  - `데이터베이스 최신 스키마 자동 동기화(db_schema_updater.py)` 수행 및 WAL 임시 정널 파일 깔끔하게 정리.
  - 웹 및 워커 데몬 정상 기동 및 Health 체크 완료.
