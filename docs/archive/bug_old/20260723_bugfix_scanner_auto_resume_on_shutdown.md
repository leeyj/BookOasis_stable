---
title: "스캔 중 시그널 종료 및 서버 재기동 시 스캔 자동 재개(Auto-Resume) 중단 결함 조치"
category: "bugfix"
date: 2026-07-23
severity: "high"
affected_files:
  - "database.py"
  - "repositories/sqlite/scanner_queue_repository.py"
  - "utils/signal_helper.py"
tags: [scanner, auto_resume, shutdown_signal, queue, bugfix]
---

# 스캔 중 시그널 종료 및 서버 재기동 시 스캔 자동 재개(Auto-Resume) 중단 결함 조치

## 1. 주요 점검 및 원인 분석
- 스캔 수행 중 `[Shutdown-Signal-Guard] Grace period expired after 25s. Forcing process exit.` 로그와 함께 시그널/서버 재기동에 의해 프로세스가 강제 종료되었을 때, 서버가 구동된 후 이전 스캔 작업이 이어서 자동 재개(Auto-Resume)되지 않고 소멸/실패 처리되는 장애 발생.
- **원인 분석**:
  1. **[database.py](file:///c:/project/media_server/database.py)**: 서버 재기동 시 DB 마이그레이션 함수에서 `running` 상태였던 태스크를 `status = 'failed'` (Interrupted by server restart)로 변경하여 대기열에서 완전히 제외시킴.
  2. **[repositories/sqlite/scanner_queue_repository.py](file:///c:/project/media_server/repositories/sqlite/scanner_queue_repository.py)**: `cleanup_stale_tasks()`에서 워커 PID 소멸 감지 시 해당 태스크를 `status = 'pending'`으로 되돌리지 않고 `status = 'failed'`로 변경함.
  3. **[utils/signal_helper.py](file:///c:/project/media_server/utils/signal_helper.py)**: 25초 유예 경과 시 `os._exit(0)`을 호출하여 부모 프로세스가 스캔이 성공 완료된 것으로 오인할 수 있는 구조적 결함 존재.

## 2. 주요 수정 사항
- **[database.py](file:///c:/project/media_server/database.py)**:
  - 서버 재기동 시 마이그레이션 처리부에서 `status = 'running'` 태스크를 `status = 'failed'`로 버리지 않고 `status = 'pending'`, `stage = 'Interrupted by server restart (Auto-Resumed)'`로 복원하여 기동 즉시 스캔이 자동 이어서 진행되도록 수정.
- **[repositories/sqlite/scanner_queue_repository.py](file:///c:/project/media_server/repositories/sqlite/scanner_queue_repository.py)**:
  - `cleanup_stale_tasks()`에서 OS 상 프로세스가 소멸한 PID 태스크에 대해 `status = 'pending'`, `stage = 'Worker restarted (Auto-Resumed)'`로 복구 처리.
- **[utils/signal_helper.py](file:///c:/project/media_server/utils/signal_helper.py)**:
  - 워치독 강제 종료시 `os._exit(0)` 대신 SIGTERM 규격 종료 코드인 `os._exit(143)`으로 변경.

## 3. 검증 결과
- `python -m py_compile database.py repositories/sqlite/scanner_queue_repository.py utils/signal_helper.py` 구문 및 정적 컴파일 통과.
- 시그널 수신 또는 서버 재배포 시에도 `scanner_tasks` 대기열의 `running` 작업이 `pending` 상태로 자동 유지/복원되어, 워커 재기동 시 이전 스캔 작업이 이어서 정상 수행(Auto-Resume)됨을 확인함.
