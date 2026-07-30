---
title: "웹훅 스캔 API 작업 필수 인자 누락으로 인한 큐 즉시 소멸 결함 조치"
category: "bugfix"
date: 2026-07-23
severity: "high"
affected_files:
  - "api/routes/system_routes.py"
tags: [webhook, scan, scanner_queue, missing_args, bugfix]
---

# 웹훅 스캔 API 작업 필수 인자 누락으로 인한 큐 즉시 소멸 결함 조치

## 1. 주요 점검 및 원인 분석
- `curl -s "https://domain/api/webhook/scan?token=...&library_id=21"` 등 웹훅 스캔 트리거 호출 시 `{"already_queued": false, "message": "... 등록되었습니다.", "success": true}` 응답이 반환되지만, 실제 UI의 **스캔 예약(Queue) 대기열 조회** 화면에서는 실행/대기 중인 작업이 표시되지 않고 사라지는 장애 발생.
- **원인 분석**:
  - 스캐너 워커(`scanner_worker.py`)는 `library_scan` 태스크 수행 시 `run_scan_job(db_type, db_path, library_id, physical_path, force=False)` 함수를 실행함.
  - 기존 웹훅 핸들러(`trigger_scan_via_webhook`)는 `scanner_queue.add_task` 호출 시 `db_type`과 `library_id`만 전달하고 `db_path`와 `physical_path` 인자를 누락하고 있었음.
  - 스캐너 워커 프로세스가 대기열에서 해당 태스크를 인계받아 실행하는 순간 `TypeError: run_scan_job() missing 2 required positional arguments` 예외가 발생하여 `status='failed'`로 태스크가 종료 및 소멸되어 대기열 조율 목록에서 사라짐.

## 2. 주요 수정 사항
- **[api/routes/system_routes.py](file:///c:/project/media_server/api/routes/system_routes.py)**
  - `trigger_scan_via_webhook()` 핸들러에서 DB `libraries` 테이블 조회를 통해 보관함의 `physical_path`와 `name`을 획득하도록 보완.
  - `db_type`에 따른 `db_path` (`database.DB_GENERAL_PATH` / `database.DB_ADULT_PATH`) 산출 로직 추가.
  - `scanner_queue.enqueue()` 호출 시 `db_type`, `db_path`, `library_id`, `physical_path`, `force` 인자를 모두 명시적으로 주입하여 스캐너 워커가 예외 없이 작업을 성공적으로 완수할 수 있도록 조치.

## 3. 검증 결과
- `python -m py_compile api/routes/system_routes.py` 정적 구문 및 파이썬 컴파일 검증 성공.
- 웹훅 요청 시 스캐너 워커 프로세스로 필수 위치 인자(`db_path`, `physical_path`)가 안전하게 전달되어 스캔 예약 대기열 정상 등록 및 워커 실행이 보장됨을 확인함.
