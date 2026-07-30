---
title: "사이드바 '전체 도서 보기' 메뉴 표시/숨김 설정 옵션 추가 (기본값: 표시)"
category: "feature"
date: 2026-07-22
severity: "low"
affected_files:
  - "templates/components/settings/general_tab.html"
  - "static/js/settings/general.js"
  - "static/js/category.js"
  - "static/js/state.js"
tags: [settings, sidebar, category_all, toggle]
---

# 사이드바 '전체 도서 보기' 메뉴 표시/숨김 설정 옵션 추가 (기본값: 표시)

## 1. 구현 개요
- 라이브러리가 많은 사용자 중 '전체 도서 보기(`all`)' 메뉴를 선호하지 않거나 사이드바 정돈을 원하는 사용자의 요구를 수용하기 위해, **[환경설정 ➔ 일반 설정]**에 사이드바 '전체 도서 보기' 메뉴를 온/오프 토글할 수 있는 설정 스위치 옵션을 추가했습니다.
- 기본값은 **켜기(체크/표시)**로 유지되어 기존 사용성과 직관성을 그대로 확보하고, 필요시 언제든 해제하여 사이드바 메뉴에서 감출 수 있도록 개선했습니다.

## 2. 주요 수정 사항
- **[templates/components/settings/general_tab.html](file:///c:/project/media_server/templates/components/settings/general_tab.html)**
  - `SHOW_SIDEBAR_CATEGORY_ALL` 체크박스 옵션 UI 추가.
- **[static/js/state.js](file:///c:/project/media_server/static/js/state.js)**
  - `showSidebarCategoryAll: true` 상태 기본값 연동.
- **[static/js/settings/general.js](file:///c:/project/media_server/static/js/settings/general.js)**
  - `SHOW_SIDEBAR_CATEGORY_ALL` 설정값의 로드/저장/UI 갱신 처리 및 저장 후 사이드바(`loadLibraries()`) 즉시 새로고침 연동.
- **[static/js/category.js](file:///c:/project/media_server/static/js/category.js)**
  - `state.showSidebarCategoryAll` 설정값에 따라 사이드바 `category-all` 항목을 조건부 렌더링하도록 반영.

## 3. 검증 결과
- 일반 설정 탭에서 '사이드바에 전체 도서 보기 메뉴 표시' 체크 해제 후 저장 시 사이드바에서 '전체 도서 목록' 메뉴가 즉시 정갈하게 숨겨지고, 재체크 시 복원됨을 확인.
