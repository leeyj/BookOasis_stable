---
title: "스캔 히스토리 크론(Cron) 자동 스캔 trigger_type 미기록 및 수동 판정 버그 수선"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "services/scheduler_service.py"
  - "api/routes/scan_routes.py"
  - "api/routes/library_routes.py"
  - "repositories/sqlite/scanner_queue_repository.py"
tags: [scan, history, cron, trigger_type, scheduler, bugfix]
---

# 🐛 버그 수정 내역: 크론(Cron) 자동 스캔 trigger_type 미기록 및 수동 판정 버그 수선

## 1. 개요 및 증상
- **증상**: 스액 히스토리 표출 시 크론 스케줄러로 구동된 예약 스캔도 모두 `수동 실행` 뱃지로 표시되던 현상.
- **원인**: 백그라운드 스케줄러(`scheduler_service.py`)가 `scanner_tasks` 대기열에 스캔 작업을 인큐할 때 `trigger_type='cron'` (또는 `is_cron=True`) 파라미터를 누락하여 대시보드 조회 시 기본값인 `manual`로 잘못 판정된 문제.

## 2. 해결 방안 (Architectural Fixes)
1. **크론 스케줄러 인자 정밀 연동 (`scheduler_service.py`)**:
   - `enqueue_scan_job` 호출 시 `trigger_type='cron'` 및 `is_cron=True` 인자를 `scanner_queue.enqueue`로 명시 전달.
2. **수동 스캔 인자 명시 (`scan_routes.py`, `library_routes.py`)**:
   - 사용자가 UI 버튼이나 API로 실행하는 스캔은 `trigger_type='manual'`, `is_cron=False`로 명시.
3. **스캔 히스토리 이력 조회 로직 보완 (`scanner_queue_repository.py`)**:
   - `get_scan_history` 판정 시 `kwargs` 내의 `trigger_type` 및 `is_cron`을 정확히 탐지하여 `크론 자동` (녹색 뱃지)과 `수동 실행` (보라색 뱃지)을 100% 명확히 구분.

## 3. 검증 결과
- 정적 검증 및 크론 스케줄 스캔 인큐 시 `kwargs`에 `"trigger_type": "cron"`이 보관되고 대시보드에 `크론 자동` 뱃지로 정확히 표시됨을 확인함.
