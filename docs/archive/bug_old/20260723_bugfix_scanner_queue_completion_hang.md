---
title: "스캔 완료 후 스캔 큐 running 고착 및 다음 스캔 미진행 버그 수정"
category: "bugfix"
date: 2026-07-23
severity: "high"
affected_files:
  - "tools/scanner/engine.py"
  - "services/scanner_queue.py"
tags: [scanner, queue, webhook, thread-blocking, try-finally, status-hang]
---

# 버그 내역

## 증상

백엔드 로그상 스캔 및 DB cleanup(`[scan-end]`)까지 정상적으로 완료되었음에도 웹 Dashboard 및 스캔 예약 대기열(Queue) UI에서 해당 라이브러리 스캔 작업이 지속적으로 **'실행 중(running)'** 상태로 표기되고, 대기 중(`pending`)인 다음 스캔 작업이 연쇄적으로 시작되지 않는 현상.

## 영향도

- **대상**: 다수의 신규/수정 도서가 존재하는 라이브러리 스캔 및 2개 이상의 연속 스캔 작업이 큐에 등록된 모든 시나리오
- **심각도**: High — 스캔은 끝났으나 큐 상태 미갱신으로 인해 후속 대기 스캔 작업이 연속적으로 실행되지 못함

---

## 근본 원인 분석

1. **스캔 종료 후 신규 도서 이벤트/웹훅의 메인 스레드 동기식 블로킹**
   - `tools/scanner/engine.py`에서 `scan-end-cleanup` 커밋 직후, `detected_new_books` 항목들에 대해 커뮤니티 웹훅(`dispatch_standard_book_event`) 및 플러그인 훅(`_dispatch_new_books_to_plugin_hooks`)이 메인 스캐너 스레드에서 **동기(Synchronous) 루프**로 개별 호출되었습니다.
   - 신규 도서 수(예: 97건)만큼 HTTP POST 요청 및 훅 작업이 순차 진행되며 메인 스캐너 함수(`_scan_library_internal` -> `run_scan_job`)의 반환이 극심하게 지연되거나 무한 블로킹 상태에 빠졌습니다.

2. **Scanner Worker Completion 상태 반영 예외 안전성 부재**
   - `services/scanner_queue.py`의 `run_scanner_worker_loop()` 내에서 작업 완료 결과 반영(`ScannerQueueRepository.update_task_result`) 부분이 `try...finally` 구조 밖에 작성되어 있었습니다.
   - 메인 스캔 스레드에서 딜레이나 예외가 발생할 경우 태스크 status를 `completed`로 갱신하는 코드가 호출되지 않아, DB `scanner_tasks` 상에서 상태가 `running`으로 영구 유지되었습니다.

---

## 수정 사항

### 1. `tools/scanner/engine.py`
- `_scan_library_internal()` 종료 시점의 웹훅 및 플러그인 훅 디스패치(`dispatch_webhook_event`, `dispatch_standard_book_event`, `_dispatch_new_books_to_plugin_hooks`)를 메인 스캐너 스레드가 아닌 **데몬 백그라운드 스레드(`threading.Thread`)**로 이관하여 메인 스케줄러가 즉시 완료 처리되도록 수정.

### 2. `services/scanner_queue.py`
- `run_scanner_worker_loop()`의 태스크 처리 및 결과 갱신 루틴을 **`try ... finally`** 블록으로 결합.
- 스캔 실행 중 어떠한 예외나 지연이 발생하더라도 `finally` 구문을 통해 `ScannerQueueRepository.update_task_result()`가 반드시 호출되어 태스크 상태가 `completed` 또는 `failed`로 확실하게 갱신되도록 개선.

---

## 해결 결과

- 스캔 엔진 작업 종료 즉시 웹 Queue UI 및 DB `scanner_tasks`의 상태가 `completed`로 즉시 업데이트됩니다.
- 대기열(`pending`)에 추가된 다음 라이브러리 스캔 작업이 지연 없이 순차적으로 연속 실행됩니다.
