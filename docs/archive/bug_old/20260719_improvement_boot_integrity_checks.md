---
title: "서비스 기동 전 DB 무결성 선제 검사 및 자동 복구/스키마 업데이트 의무화"
project: "BookOasis"
category: "improvement"
date: 2026-07-19
tags: [boot, integrity-check, auto-recovery, schema-update, bugfix]
---

# 🚀 서비스 기동 전 DB 무결성 선제 검사 및 자동 복구/스키마 업데이트 의무화

## 1. 개선 배경 및 목적
- 이전 자가 치유(와치독) 기획을 파기하고, 서비스 기동(시작/재구동) 시점에 데이터베이스 파일 손상(`malformed`) 상태가 있을 경우 무작정 서비스를 띄우지 않고 선제적으로 이를 감지하여 강제 자동 복구를 수행하며, 복구 성공 후에만 최신 스키마를 강제 동기화하고 서비스를 정상 시작하도록 구성하여 부트 프로세스 정합성을 극대화하기 위함입니다.

## 2. 주요 개선 사항
- **[manage.sh](file:///c:/project/media_server/manage.sh) start() 함수 개선**:
  - 서비스 기동 직전 SQLite `integrity_check` 쿼리를 가동하여 `media_general.db` 및 `media_adult.db` 무결성을 확인합니다.
  - 무결성 실패(DB 손상) 감지 시 즉시 `tools/db_recovery.py --yes` 스크립트를 호출하여 덤프 방식 자동 복구를 가동합니다. 복구 실패 시 안전을 위해 프로세스 구동을 차단합니다.
  - 무결성 검증 통과 후 `tools/db_schema_updater.py`를 무조건 먼저 가동해 누락된 스키마 컬럼 및 인덱스 동기화 및 WAL 정리를 완료한 뒤 Gunicorn과 스캐너 워커를 실행합니다.
- **[entrypoint.sh](file:///c:/project/media_server/entrypoint.sh) 도커 기동 사전 검사 추가**:
  - 도커 컨테이너 기동(gosu/root 프로세스 교체 직전) 시에도 동일하게 DB 무결성 체크 및 자동 복구/최신 스키마 동기화 절차를 의무적으로 먼저 통과하도록 선제 가드 코드를 통합 주입했습니다.

## 3. 검증 결과
- 수정 완료 후 `deploy.py`를 실행하여 원격지 배포 및 재시작 헬스 체크 정상 통과를 완료하였습니다.
- 기동 전 스키마 업데이트 스크립트 실행 및 WAL 임시 정널 파일이 깨끗하게 트런케이트 및 정리 완료되었음을 원격 기동 로그를 통해 정상 검증했습니다.
