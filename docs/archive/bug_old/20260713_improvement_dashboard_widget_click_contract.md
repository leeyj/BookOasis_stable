---
title: "대시보드 위젯 카드 클릭 계약 및 라우팅 지원"
project: "BookOasis"
category: "improvement"
date: 2026-07-13
tags: [improvement, dashboard, plugin, widget]
---

# 대시보드 위젯 카드 클릭 계약 및 라우팅 지원

## 1. 개요 및 요구사항
- 외부 커뮤니티 개발자가 개발한 플러그인(최근 사용자 활동 등)의 카드 아이템을 대시보드에서 클릭했을 때, 해당 도서의 상세 단행본 목록 화면(상세 뷰)으로 이동하거나 단일 도서인 경우 뷰어(책 읽기 화면)를 즉시 활성화하는 라우팅 계약(Click Contract)이 필요함.
- 플러그인의 `script.js`가 대시보드 로드 시 실행되지 않고 데이터만 공급받는 제약이 있어, 공통 UI 로더 단에서 라우팅에 맞는 분기 처리 및 클릭 계약, DOM 데이터 속성 주입이 지원되어야 함.

## 2. 조치 사항
- **대시보드 공통 위젯 아이템 렌더러 개선 (`static/js/dashboard.js`)**:
  - `loadDashboardWidgetData`에서 위젯 아이템 데이터를 순회하며 DOM을 빌드할 때, 아이템 내에 외부 아웃링크(`link`가 `#`가 아닌 경우)가 없는 경우 클릭 처리기(`onclick`)를 다음과 같이 분기하여 자동 바인딩함:
    1. **단일 도서 뷰어 직접 열기**: `book_id` (또는 `bookId`)와 `file_format` (또는 `format`)이 존재하는 경우, 클릭 시 전역 `window.openReader`를 실행하여 뷰어를 즉시 구동.
    2. **시리즈 상세 페이지로 이동**: 위 항목이 불충분하고 `series_name` (또는 `series`)만 존재하는 경우, 클릭 시 전역 `window.openBookDetail` 함수를 실행하여 시리즈 상세 리스트로 라우팅.
  - 마우스 오버 시 사용자가 클릭 가능함을 명시적으로 파악할 수 있도록 컨테이너 스타일 주입 (`cursor: pointer;`).
  - DOM 탐색 및 분석용으로 컨테이너 마크업 내 `data-series-name`, `data-library-id`, `data-book-id`, `data-file-format` 메타 속성을 명시적으로 제공함.

## 3. 해결 확인 및 영향도
- 최근 사용자 활동 위젯 등의 카드에 마우스 커서를 올렸을 때 포인터로 변경되며, 클릭 시 전달된 데이터 사양에 따라 뷰어(책 읽기)가 즉시 구동되거나 해당 도서의 상세 리스트 화면으로 안전하게 라우팅되는 것을 최종 검증함.
