---
title: "스캔 에러 리포트 탭 내 최근 스캔 히스토리(카테고리명, 경과시간, 시작/종료시간, 수동/크론 종류) 20건 표출"
category: "feature"
date: 2026-07-23
affected_files:
  - "repositories/sqlite/scanner_queue_repository.py"
  - "api/routes/scan_routes.py"
  - "templates/components/settings/reports_tab.html"
  - "static/js/settings/reports.js"
tags: [scan, history, reports, dashboard, ui, feature]
---

# 🚀 신규 기능: 리포트 뷰어 탭 내 최근 스캔 히스토리 (최대 20건) 표출

## 1. 개요 및 배경
- **배경**: 환경설정 ➔ [리포트 뷰어] 탭의 빈 공간을 활용하여 최근 수행된 스캔 작업 이력(카테고리명, 상대 경과 시간, 시작/종료 시각, 스캔 종류: 수동/크론)을 한눈에 모니터링할 수 있는 대시보드를 추가함.
- **주요 조건**:
  - 백그라운드 무한 수집인 레이지스캔(`lazy_scan`)은 깔끔히 제외.
  - 최신 20건 한정 표출 (`LIMIT 20`).
  - `상대 경과 시각` 컬럼 제공 (`방금 전`, `30분 전`, `2시간 전`, `1일 전`, `2일 전` 등).

## 2. 주요 구현 내용
1. **백엔드 DB 쿼리 및 REST API (`scanner_queue_repository.py`, `scan_routes.py`)**:
   - `ScannerQueueRepository.get_scan_history(limit=20)` 구현: `task_type != 'lazy_scan'` 조건으로 `scanner_tasks` 및 `libraries` 데이터 조인.
   - `GET /api/media/scan-history`: 상대 경과 시각 계산 및 20건의 JSON 응답 반환.
2. **프론트엔드 UI/UX (`reports_tab.html`, `reports.js`)**:
   - 리포트 탭 상단에 **[스캔 실행 이력 (최근 20건)]** 프리미엄 카드 테이블 배치.
   - `수동 실행`(푸른색/보라색 뱃지) vs `크론 자동`(녹색/주황색 뱃지) 시각 구분.

## 3. 검증 결과
- 정적 검증 및 20건 최신 스캔 이력이 상대 시간과 함께 정상 표출됨을 확인함.
