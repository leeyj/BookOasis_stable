---
title: "DB 자동 복구 도구(db_recovery.py) FTS5 소거 및 스크립트 전반 검토 정돈"
category: "refactor"
date: 2026-07-22
severity: "medium"
affected_files:
  - "tools/db_recovery.py"
  - "manage.sh"
  - "entrypoint.sh"
tags: [db_recovery, fts5, manage.sh, entrypoint.sh, refactor]
---

# DB 자동 복구 도구(db_recovery.py) FTS5 소거 및 스크립트 전반 검토 정돈

## 1. 검토 및 정돈 개요
- FTS5 완전 소거 정책에 따라 연관된 시스템 지원 도구 및 기동 스크립트([manage.sh](file:///c:/project/media_server/manage.sh), [entrypoint.sh](file:///c:/project/media_server/entrypoint.sh), [db_recovery.py](file:///c:/project/media_server/tools/db_recovery.py))를 정밀 검토 및 보완했습니다.

## 2. 검토 및 수정 결과
1. **[manage.sh](file:///c:/project/media_server/manage.sh) & [entrypoint.sh](file:///c:/project/media_server/entrypoint.sh)**
   - 두 스크립트는 이미 SQLite 무결성 검사(`integrity_check`) 및 프로세스 종료 순서(스캐너 우선 종료 -> 웹서버 마감)를 완벽히 준수하고 있으며 FTS5 전용 의존 구문이 없어 안전함을 확인했습니다.
2. **[tools/db_recovery.py](file:///c:/project/media_server/tools/db_recovery.py)**
   - STEP 3의 `rebuild_fts_index` 구문을 FTS5 재빌드 방식에서 `cleanup_legacy_fts_index`를 통한 구형 가상 테이블 디스크 완진 소거 방식으로 갱신했습니다.
   - DB 복구 시 FTS5 가상 테이블 및 그림자 세그먼트 생성 쿼리를 필터링하는 조건은 복구 시 구형 세그먼트 주입 방지를 위해 그대로 유지하여 안전성을 높였습니다.

## 3. 검증
- `python deploy.py` 정상 완료: 원격 재기동 시 복구 및 스키마 검사 프로세스가 깔끔하게 완료되고 서버(`PID: 2402129`) 및 워커(`PID: 2402188`)가 정상 작동함.
