---
title: "레이지 스캐너 종료 시 DB 무결성 파손 (malformed) 결함 수정"
date: "2026-07-21"
author: "Antigravity AI"
status: "Resolved"
impact: "Critical"
components:
  - "tools/lazy_scanner.py"
  - "manage.sh"
  - "entrypoint.sh"
  - "core.py"
  - "utils/signal_helper.py"
---

# 레이지 스캐너 종료 시 DB 무결성 파손 결함 수정

## 현상
서버 재기동/종료 명령 시 `database disk image is malformed` 오류 발생과 함께 `media_general.db` 데이터베이스가 파손되는 심각한 오류 발생.

```text
[Graceful-Shutdown] atexit 수신, 서버 종료 프로세스 시작...
[DB-Shutdown] 모든 DB 커넥션 풀 종료 시작...
[DB-Shutdown] WAL 체크포인트 완료: /home/az001a/Script/media_server/db/media_general.db
...
[DB-Sanity] general DB — DB 접속 실패: database disk image is malformed
```

## 원인 분석
1. **프로세스 종료 순서 역전 (`manage.sh`)**: 메인 웹 서버 프로세스를 먼저 종료하면서 웹 서버의 `atexit`이 DB 커넥션 풀을 닫고 WAL 체크포인트를 수행함. 이 시점에 백그라운드 독립 프로세스인 `lazy_scanner.py`는 종료 신호를 받지 못하고 계속 DB 조회/트랜잭션 커밋을 시도하여 SQLite WAL/SHM 트랜잭션 충돌 및 파손 유발.
2. **`lazy_scanner.py` 시그널 핸들러 미등록**: `run_lazy_cover_extraction()` 진입 시 SIGTERM/SIGINT 핸들러(`register_shutdown_handlers`)가 등록되어 있지 않아, SIGTERM 수신 시 트랜잭션 롤백 및 우아한 커넥션 닫기가 수행되지 못함.
3. **웹 서버 Graceful Shutdown 시 외부 스캐너 프로세스 확인 부재 (`core.py`)**: 웹 서버가 DB 커넥션 풀을 닫기 전 실행 중인 외부 레이지 스캐너 프로세스를 감지하고 정리를 대기하는 방어 장치 결여.

## 수정 사항

1. **`manage.sh` & `entrypoint.sh` (종료 순서 전면 개편)**
   - 호스트 환경(`manage.sh`) 및 도서/컨테이너 환경(`entrypoint.sh`) 모두 종료 순서를 **[1] 스캐너 워커 -> [2] 레이지 스캐너 -> [3] 웹 서버** 순으로 수정.
   - `entrypoint.sh`에 `lazy_scanner.py` 프로세스 감지 및 SIGTERM 전파 로직 추가.
   - 스캐너 프로세스들이 DB 커넥션을 롤백/닫고 완벽히 마감한 후 웹 서버가 최종 DB 풀 종료 및 WAL 체크포인트를 치도록 순서 보장.

2. **`tools/lazy_scanner.py` (시그널 핸들러 및 DB 안전 마감 / 세션 누적 용량 제한 보강)**
   - `run_lazy_cover_extraction()` 시작 시 `register_shutdown_handlers()` 등록.
   - DB 연결 시 `PRAGMA busy_timeout = 30000;` 설정하여 락 대기 안정화.
   - `stop_requested` 수신 시 `conn.rollback()` 및 `conn.close()`를 안전하게 호출하여 진행 중이던 DB 트랜잭션을 깨끗이 마감하고 종료.
   - **`LAZY_SCAN_MAX_BATCH_SIZE_MB` (기본 1024MB / 1GB) 도입**: 세션 내 처리한 파일의 누적 크기를 추적하여, 한도 도달 시 남아있는 작업은 다음 Cron 주기로 안전하게 미루고 정상 마감(메모리 누적 폭주 예방).

3. **`core.py` (웹 서버 Shutdown 2차 방어막 구축)**
   - `_graceful_shutdown()` 실행 시 `psutil`을 통해 실행 중인 외부 `lazy_scanner.py` 프로세스가 존재하는지 확인하고, SIGTERM을 송신해 최대 5초간 안전 마감을 대기한 후 DB 풀(`shutdown_all_pools()`)을 닫도록 방어벽 보강.

## 검증
- 백그라운드 레이지 스캐너가 무거운 스캔을 진행 중인 상태에서 `./manage.sh stop` 및 서버 재기동 시, 레이지 스캐너가 시그널을 수신하여 트랜잭션을 롤백하고 깔끔히 종료된 후 웹 서버가 DB 풀을 마감함.
- `database disk image is malformed` 결함 완전 소거 확인.
