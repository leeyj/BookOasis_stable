---
title: "웹훅 스캔 API 전역 인증 체크 우회 (bypass) 수정"
category: "bugfix"
date: 2026-07-23
severity: "high"
affected_files:
  - "api/auth.py"
tags: [webhook, scan, auth, login_required, bugfix]
---

# 웹훅 스캔 API 전역 인증 체크 우회 (bypass) 수정

## 1. 주요 점검 및 원인 분석
- `curl -s 'https://books.zeeps.net/api/webhook/scan?token=...&library_id=13'` 등 웹훅을 통한 실시간 스캔 트리거 호출 시 `{"error": "로그인이 필요합니다.", "success": false}` (401 Unauthorized) 응답이 반환되는 장애 발생.
- **원인 분석**:
  - `api/auth.py`의 `@auth_bp.before_app_request`로 등록된 `check_authentication()` 함수는 모든 HTTP 요청에 대해 세션 기반 미로그인 시 401 에러를 반환함.
  - `/api/webhook/scan` API는 자체 보안 토큰(`WEBHOOK_TOKEN`)으로 승인하도록 구현되어 있으나, `check_authentication()`의 예외 경로(`static`, `health`, `opds`, `covers` 등) 목록에 `/api/webhook/` 경로는 포함되어 있지 않았음.
  - 결과적으로 라우트 핸들러인 `trigger_scan_via_webhook()`에 도달하기 전 `before_app_request` 수준에서 로그인 미인증으로 먼저 차단됨.

## 2. 주요 수정 사항
- **[api/auth.py](file:///c:/project/media_server/api/auth.py)**
  - `check_authentication()` 내 미인증 예외 처리 조건식에 `request.path.startswith('/api/webhook/')` 우회 규칙을 추가.
  - 웹훅 요청에 대해 세션 로그인 체크를 우회하고, 웹훅 라우트 핸들러 내부의 `WEBHOOK_TOKEN` 검증 로직으로 정상 전달되도록 수정.

## 3. 검증 결과
- 웹훅 API 요청 시 세션 쿠키 없이 토큰(`token`) 파라미터만으로 `WEBHOOK_TOKEN` 검증 및 보관함 실시간 스캔 주입 기능이 정상 작동함을 확인함.
