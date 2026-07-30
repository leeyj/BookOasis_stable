---
title: "스캐너 워커 프로세스 중복 생성 방지 및 DB 손상/웹 대시보드 강제 종료 버그 수정"
category: "bugfix"
date: 2026-07-24
severity: "critical"
affected_files:
  - "core.py"
  - "repositories/sqlite/scanner_queue_repository.py"
tags: [scanner, worker, duplicate-execution, db-corruption, gunicorn, race-condition, bugfix]
---

# 🐛 버그 수정 내역: 스캐너 워커 프로세스 중복 생성 방지 및 DB 손상/웹 대시보드 강제 종료 버그 수정

## 증상

A 카테고리 스캔 진행 도중 B 카테고리 스캔을 추가(또는 신규 등록/수정)할 때:
1. 실제 스캔은 A 카테고리를 진행하고 있음에도 대시보드 및 스캔 큐 상에서는 B 카테고리를 스캔하고 있는 것으로 오표시됨.
2. A 카테고리 스캔이 완료되는 시점에 웹 대시보드가 강제 종료(크래시)되고 SQLite DB가 손상(`database disk image is malformed`)되는 현상 발생.

## 원인 분석

1. **Gunicorn / Flask 멀티 프로세스 환경에서의 워커 중복 생성 (`core.py`)**:
   - `core.py`의 `ensure_scanner_worker_running()`이 단순 Python 인메모리 변수(`_worker_process is None`)만을 체크함.
   - Gunicorn이나 멀티 프로세스 웹 서버 환경에서는 HTTP 요청을 처리하는 개별 웹 프로세스 메모리 상에서 `_worker_process`가 `None`이므로, OS 상에 이미 A 카테고리를 스캔 중인 스캐너 워커(`tools/scanner_worker.py`)가 1개 살아있음에도 불필요하게 **두 번째 스캐너 워커 프로세스**를 새로 띄움.

2. **대시보드 큐 현황 쿼리의 오표시 (`ScannerQueueRepository.fetch_queue_status`)**:
   - 새로 떠오른 두 번째 워커 프로세스가 큐에서 B 카테고리 태스크를 `running`으로 선점하면서 `started_at`을 최신 시각으로 기록함.
   - 대시보드의 대기열 현황 API가 `WHERE status = 'running' ORDER BY started_at DESC LIMIT 1`로 쿼리하여, 나중에 픽업된 B 카테고리 태스크를 스캔 중 현황으로 1위 반환하게 됨.

3. **복수 워커의 SQLite 동시 쓰기로 인한 DB 손상 및 웹 서버 다운**:
   - 2개 이상의 스캐너 워커 프로세스가 단일 SQLite DB(`media_general.db`) 파일에 동시에 대량의 쓰기 트랜잭션을 집중 수행함.
   - SQLite 락 경합 및 트랜잭션 파괴로 DB 파일이 손상되고, 스캔 완료 처리 지점에서 치명적 DB 에러로 웹 서버 프로세스가 연쇄 강제 종료됨.

---

## 수정 사항

### 1. OS 레벨 워커 프로세스 생존 검사 도입 (`core.py`)
- `is_scanner_worker_running_os()` 헬퍼 함수 구현:
  - `psutil`을 활용하여 OS 프로세스 목록 상에서 `tools/scanner_worker.py` 프로세스가 실제 살아있는지 감시.
- `ensure_scanner_worker_running()` 수정:
  - 메모리 레퍼런스(`_worker_process`)뿐만 아니라 `is_scanner_worker_running_os()`를 함께 검사하여, 이미 OS 상에 1개 이상의 스캐너 워커가 존재하면 중복 생성을 즉시 차단함.

### 2. Single-Worker Lock 및 대시보드 쿼리 보강 (`repositories/sqlite/scanner_queue_repository.py`)
- `try_acquire_task()`에 이중 방어선 배치:
  - 태스크 선점 시 이미 DB 상에 `status = 'running'`인 태스크가 존재하는 경우 동시 선점(`return False`)을 원자적으로 막음.
- `fetch_queue_status()` 쿼리 보완:
  - `running` 작업 조회 정렬 조건을 `ORDER BY started_at ASC`로 변경하여, 최초에 시작된 태스크가 대시보드 1위 현황으로 유지되도록 보장.

---

## 해결 결과

- 스캔 진행 도중 새로운 스캔 작업을 추가하거나 라이브러리를 등록하더라도 워커 프로세스가 이중 기동되지 않고 **단일 워커 프로세스가 큐의 작업들을 순차적으로(Sequential) 처리**하도록 원천 보호됨.
- 대시보드상에서 현재 스캔 중인 카테고리가 오표시되는 현상이 완벽히 해소됨.
- 동시 쓰기로 인한 SQLite DB 손상 및 웹 서버 강제 종료 현상이 근본적으로 방지됨.
