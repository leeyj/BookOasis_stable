---
title: "스캐너 라이브러리 스캔 내 DB 커넥션 누수 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, scanner, db-leak, connection-pool]
---

# 🐛 스캐너 라이브러리 스캔 내 DB 커넥션 누수 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 배포 이후 웹 서비스 사용 시 화면 목록이 갱신되지 않고 무한 대기 상태에 빠지는 장애가 재발함.
- 브라우저 콘솔에서 `/api/media/libraries?type=general` 및 `/api/media/history?type=general` 호출이 500 Internal Server Error로 실패함을 확인함.
- 서버 측 진단 결과: `Database connection pool exhausted. Timeout waiting for connection` 오류로 확인됨.

## 2. 원인 분석 (Root Cause Analysis)
- `tools/scanner.py`의 `scan_library` 함수 내에서 라이브러리 물리 디렉터리 스캔을 마친 후 정상 종료되는 맨 마지막 흐름에서 `conn.commit()` 및 `conn.close()`를 처리하지 않고 함수를 나감.
- 결과적으로 스캐너가 한 번 동작할 때마다 획득한 SQLite 커넥션이 회수되지 않고 풀(Pool)에 유휴 상태가 아닌 상태로 그대로 방치(Leak)됨.
- Gunicorn의 싱글 프로세스/멀티스레드 구조 상, 풀 크기(5개)만큼 스캔이 구동된 이후에는 풀이 완전히 고갈되어 이후 웹 API 요청이 데이터베이스 커넥션을 획득하지 못해 영구 행(Hang) 및 타임아웃 500에러를 초래하게 됨.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [scanner.py](file:///c:/project/media_server/tools/scanner.py)
  - `scan_library` 함수 맨 최하단인 삭제 감시 루프(`for dp in deleted_paths:`) 실행 뒤에 누락되었던 **`conn.commit()`** 및 **`conn.close()`** 구문을 정확히 추가함.
  - 이로 인해 스캔 작업이 무사히 종료되는 시점에 영구 미결 트랜잭션이 최종 반영되고, 해당 데이터베이스 커넥션이 정상적으로 커넥션 풀에 반환되도록 조치함.

## 4. 결과 검증 (Verification Results)
- 코드를 원격 홈 서버에 배포한 후 데몬을 재기동함.
- API 진단용 파이썬 스크립트 실행 결과, `/api/media/libraries`가 1초 미만의 속도로 정상 응답(200 OK)하고 전체 JSON 도서관 리스트를 올바르게 반환함을 검증 완료함.
