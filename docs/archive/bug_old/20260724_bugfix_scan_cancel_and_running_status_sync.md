---
title: "스캔 대기열 취소(Cancel) 연동 누락 및 실행 중 태스크 취소 거부 결함 조치"
category: "bugfix"
date: 2026-07-24
severity: "critical"
affected_files:
  - "repositories/sqlite/scanner_queue_repository.py"
  - "tools/scanner/engine.py"
tags: [scanner_cancel, scan_status, cancelled, queue, engine_abort, bugfix]
---

# 🐛 버그 수정 내역: 스캔 대기열 취소(Cancel) 연동 누락 및 실행 중 태스크 취소 거부 결함 조치

## 증상

1. 스캔 대기열 조회 화면에서 [취소] 버튼을 눌렀음에도 불구하고, 실제 서버 터미널 및 스캐너 워커 프로세스에서는 스캔 작업이 중단되지 않고 계속 동작하는 현상.
2. 대시보드 UI 대기열에는 `대기 중` 또는 `취소`로 표시되나 실제 스캐너 엔진은 백그라운드에서 스캔을 지속하여 락 경합 및 대기열 상태 오표시가 발생하는 현상.

---

## 원인 분석

1. **`cancel_task()`의 실행 중(`running`) 태스크 취소 거부**:
   - `scanner_queue_repository.py`의 `cancel_task()`가 `WHERE status = 'pending'` 조건으로만 쿼리를 수행하여, 이미 `running` 상태로 실행 중인 스캔 태스크의 취소 요청을 거부함.
2. **`libraries.scan_status` 갱신 누락**:
   - 대기열에서 취소 버튼을 눌렀을 때 `scanner_tasks.status`만 변경을 시도하고, 스캐너 엔진이 참조하는 `libraries.scan_status = 'cancelling'` 업데이트가 누락됨.
   - 스캐너 엔진(`engine.py`)은 `libraries.scan_status == 'cancelling'` 만 체크하였기 때문에 취소 요청을 전혀 인지하지 못하고 스캔을 계속 진행함.

---

## 수정 사항

### 1. [repositories/sqlite/scanner_queue_repository.py](file:///c:/project/media_server/repositories/sqlite/scanner_queue_repository.py)
- `cancel_task()` 수정: `status IN ('pending', 'running')` 조건으로 확대하여 실행 중인 스캔 작업도 즉시 취소 처리.
- `library_scan` 작업 취소 시 해당 라이브러리의 `libraries.scan_status = 'cancelling'` 을 원자적으로 업데이트하여 진행 중인 스캐너 엔진이 실시간으로 감지하도록 연동.

### 2. [tools/scanner/engine.py](file:///c:/project/media_server/tools/scanner/engine.py)
- 스캔 루프 내 취소 감지 주기를 매 3개 폴더 마다로 단축.
- `libraries.scan_status == 'cancelling'` 뿐만 아니라 `scanner_tasks.status == 'cancelled'` 상태도 함께 2중으로 검사하여, 취소 요청 감지 즉시 안전하게 덤프 데이터를 플러시하고 스캔을 조기 중단(Safely Abort)하도록 보완.

---

## 해결 결과

- 대시보드 대기열 및 스캔 중 [취소] 버튼 누르는 즉시 진행 중이던 스캐너 워커 엔진이 작업을 즉시 안전 중단함.
- 스캔 취소 후 불필요한 스캔 동작이나 락 경합, DB 손상(malformed) 재발이 원천 차단됨.
