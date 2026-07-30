---
title: "run_scan_job unexpected keyword argument trigger_type 예외 수선"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "services/scheduler_service.py"
tags: [scanner, run_scan_job, typeerror, kwargs, bugfix]
---

# 🐛 버그 수정 내역: run_scan_job unexpected keyword argument 'trigger_type' 예외 수선

## 1. 개요 및 증상
- **증상**: 스캐너 워커 프로세스가 대기열 태스크를 처리 중 `run_scan_job() got an unexpected keyword argument 'trigger_type'` TypeError 예외가 발생하며 태스크가 실패 처리되는 현상.
- **원인**: 스캔 이력의 크론/수동 구분을 위해 인큐 파라미터로 `trigger_type` 및 `is_cron`을 추가했으나, `run_scan_job` 함수 서명(Signature)에 해당 가변 인자 선언이 누락되어 발생함.

## 2. 해결 방안 (Architectural Fixes)
1. **`run_scan_job` 함수 서명 가변 인자 확장 (`services/scheduler_service.py`)**:
   - `run_scan_job` 함수 서명에 `trigger_type='manual'`, `is_cron=False`, `**kwargs` 가변 파라미터를 추가하여 큐에서 포워딩되는 모든 파라미터를 에러 없이 수용하도록 처리함.

```python
def run_scan_job(db_type, db_path, library_id, physical_path, force=False, initial_add_scan=False, trigger_type='manual', is_cron=False, **kwargs):
```

## 3. 검증 결과
- 정적 구문 검사 및 스캔 태스크 구동 시 `TypeError` 없이 100% 정상 작동함을 확인함.
