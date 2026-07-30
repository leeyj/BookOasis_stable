---
title: "Lazy Scanner 중간 상태(exit_pending) 및 강제 재등록(force_requeue) 보정"
date: "2026-07-21"
tags:
  - bugfix
  - scanner
  - lazy_scan
  - oom
---

# 🐛 버그 수정 내역 (Bugfix)

## 1. 개요 및 영향도
- **현상**: `lazy_scan` 태스크 수행 도중 RAM 환수(exit code 10) 또는 OOM/프로세스 강제 종료가 발생할 경우, DB(`scanner_tasks`)의 작업 상태가 `running` 또는 `pending` 상태에 갇혀(Stuck), 이후 스케줄러 재기동이나 API 강제 요청 시 `force_requeue`가 정상 적용되지 않고 계속 무시/대기하는 현상이 발생함.
- **영향 범위**: `services/scanner_queue.py`, `repositories/sqlite/scanner_queue_repository.py`, `database.py`.

## 2. 주요 수정 사항

1. **`repositories/sqlite/scanner_queue_repository.py`**:
   - `update_task_to_pending` 함수에 `force_requeue=False` 파라미터를 추가하여, `force_requeue=True`일 때 기존 상태가 `running` 또는 `exit_pending`이더라도 `pending` 상태로 갱신할 수 있도록 허용.
   - 중간 임의 상태 조정을 위한 `update_task_status(task_id, status, stage=None, error_message=None)` 메서드 구현.

2. **`services/scanner_queue.py`**:
   - `ScannerQueue.enqueue`에서 `ScannerQueueRepository.update_task_to_pending` 호출 시 `force_requeue=force_requeue` 전달.
   - `_process_lazy_scan` 서브배치 루프에서 RAM 환수(exit code 10)로 서브-배치가 마감될 때 DB 상태를 `exit_pending`으로 중간 기록하여 고착을 방지하고 상태 투명성 확보.

3. **`database.py`**:
   - 서버 재시작 및 DB 마이그레이션 시 `exit_pending` 상태의 고착된 태스크를 `pending`으로 자동 복구(Auto-Resume)하는 초기화 로직 추가.

## 3. 검증
- 모듈 구동 테스트 완료 (`python -c "import database..."`, `python -c "from services.scanner_queue import ScannerQueue..."`).
