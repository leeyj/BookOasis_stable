---
title: "백그라운드 스캔 및 대기열 실행 중 카테고리 삭제 시도 방어 차단 조치"
category: "feature"
date: 2026-07-22
severity: "medium"
affected_files:
  - "services/category_service.py"
tags: [category, delete, scan_status, scanner_queue, protection]
---

# 백그라운드 스캔 및 대기열 실행 중 카테고리 삭제 시도 방어 차단 조치

## 1. 개요 및 안전 목적
- 카테고리(도서관)가 백그라운드 스캔 중이거나 대기열에 등록된 상태에서 사용자가 카테고리를 삭제할 경우, 스캐너의 DB 쓰기 트랜잭션과 연쇄 삭제 트랜잭션 간 충돌이 발생해 Foreign Key 및 레코드 파손이 우려되던 위험을 완전히 억제했습니다.

## 2. 주요 구현 사항
- **[services/category_service.py](file:///c:/project/media_server/services/category_service.py)**
  - `delete_library(db_type, library_id)` 수행 상단에 스캔 상태 및 대기열 이중 검증 로직 추가.
  1. `scan_status` 검증: 해당 라이브러리의 상태가 `scanning` 또는 `cancelling`일 경우 삭제 요청을 거부하고 `"현재 카테고리가 스캔 진행 중입니다. 스캔이 완료된 후 삭제해 주세요."` 예외 메시지 반환.
  2. `scanner_queue` 검증: `scanner_queue.get_queue_status()`를 조회하여 삭제 대상 라이브러리의 `library_scan` 또는 `cover_scan` 작업이 실행 중이거나 대기(pending) 상태일 경우 삭제를 즉시 차단.

## 3. 검증 결과
- 스캔 구동 중 웹 UI 및 API를 통한 카테고리 삭제 시도가 안전하게 차단되며, 스캔이 완전히 끝난 후나 대기열 취소 시에만 삭제가 허용됨을 확인.
