---
title: "Lazy Scanner 용량 한도 조기 탈출 및 SIGTERM 미반응 보정"
date: "2026-07-21"
tags:
  - bugfix
  - scanner
  - lazy_scan
---

# 🐛 버그 수정 내역 (Bugfix)

## 1. 개요 및 영향도
- **현상**: 
  1. `general` DB 스캔 중 용량 한도(2048MB)에 달성하여 exit code 10 재기동이 필요함에도, 바깥쪽 `for db_type in db_types:` 루프를 즉시 조기 탈출하지 않아 다음 순서인 `adult` DB 검사를 0.001초 동안 무의미하게 실행하고 나가는 문제.
  2. 스캐너가 대량 도서 레코드의 파일 물리 존재 여부(`os.path.exists`) 점검 루프를 도는 도중 종료 시그널(SIGTERM)이 수신될 경우, 점검 순회가 끝날 때까지 롤백 반응이 지연되는 문제.
- **영향 범위**: `tools/lazy_scanner.py`.

## 2. 주요 수정 사항
1. `tools/lazy_scanner.py`의 `run_lazy_cover_extraction`:
   - `batch_limit_reached` 또는 `stop_requested`가 `True`일 경우, `for db_type` outer 루프를 즉시 `break`하도록 조기 탈출 로직 추가.
   - `for book in books:` 파일 물리 점검 루프 내부에도 `if stop_requested: break` 가드를 추가하여 SIGTERM 수신 시 즉시 물리 점검을 멈추고 롤백하도록 보장.

## 3. 검증
- 모듈 구동 테스트 완료 (`python -c "import tools.lazy_scanner..."`).
- 배포 스크립트 실행 완료.
