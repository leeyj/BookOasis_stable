---
title: "웹훅 스캔 API (/api/webhook/scan) 검증 및 중복 등록 응답 보완"
category: "bugfix"
date: 2026-07-22
severity: "medium"
affected_files:
  - "api/routes/system_routes.py"
tags: [webhook, scan, api, bugfix]
---

# 웹훅 스캔 API (/api/webhook/scan) 검증 및 중복 등록 응답 보완

## 1. 주요 점검 및 원인 분석
- `curl -s "http://IP:5930/api/webhook/scan?token=TOKEN&library_id=ID&type=general"` 웹훅 API 호출 시 발생할 수 있는 주요 예외 요소 점검:
  1. `WEBHOOK_TOKEN` 설정 미입력 또는 토큰 불일치 시 `401 Unauthorized` 반환.
  2. 존재하지 않는 `library_id` 입력 시 DB 예외 대신 `404 Not Found`와 직관적 에러 반환.
  3. 스캔 작업이 이미 큐에 대기/실행 중일 때 `already_queued: true` 안내와 함께 정상 HTTP 200 반환.
  4. 강제 재등록 옵션(`&force=1`) 매개변수 지원 추가.

## 2. 주요 수정 사항
- **[api/routes/system_routes.py](file:///c:/project/media_server/api/routes/system_routes.py)**
  - `library_id` 정수형 검증 및 해당 보관함 존재 여부 사전 체크 추가.
  - `scanner_queue.add_task(...)` 결과인 `enqueued` 반환값을 확인하여 대기열 등록 여부와 중복 상태를 분기 응답.
  - `force=1` 파라미터 전달 시 기존 대기열 작업을 강제 재등록하는 옵션 추가.

## 3. 검증 결과
- 웹훅 호출 시 올바른 토큰과 library_id 전달 시 스캔 대기열 주입 및 세부 응답 메시지가 완벽히 작동함을 확인함.
