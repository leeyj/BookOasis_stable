---
title: "도서 보관함 헤더 카테고리 명칭 직접 출력 UI 다듬기"
category: "ui"
date: 2026-07-22
severity: "low"
affected_files:
  - "templates/components/tab_media_library.html"
  - "static/js/tab_media_library.js"
  - "static/css/style.css"
tags: [ui, header, category_name, clean_design]
---

# 도서 보관함 헤더 카테고리 명칭 직접 출력 UI 다듬기

## 1. 개요 및 변경 목적
- 기존에는 상단 타이틀에 고정 텍스트 "도서 보관함"과 함께 옆에 캡슐 알약 형태의 뱃지로 `[라노벨(GDS)]`와 같이 별도 출력되어 중복되고 어색한 느낌이 있었습니다.
- 사용자 요청에 따라 "도서 보관함" 고정 텍스트+뱃지 조합 대신 선택한 카테고리 명칭(예: **"라노벨(GDS)"**, 메인 홈 선택 시 **"도서 보관함"**)이 헤더 메인 타이틀 위치에 직접 깔끔하게 출력되도록 UI를 다듬었습니다.

## 2. 주요 수정 사항
- **[templates/components/tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**
  - 중복되던 뱃지 태그를 제거하고, `current-category-indicator` 요소가 메인 타이틀 텍스트 위치에 직접 위치하도록 마크업 단순화.
- **[static/js/tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)**
  - `getSystemCategoryLabel('home')` 기본값을 기존 "Home" 대신 "도서 보관함"으로 지정하여 메인 홈 뷰 선택 시 "도서 보관함"이 타이틀로 깔끔하게 노출되도록 보완.
- **[static/css/style.css](file:///c:/project/media_server/static/css/style.css)**
  - `.current-category-indicator-title` 스타일을 정의하여 메인 폰트 타이틀 크기(`1.5rem`, `font-weight: 700`, `#fff`)와 가독성을 보장.

## 3. 검증 결과
- 좌측 사이드바에서 카테고리 변경 시(예: '라노벨(GDS)', '만화(로컬)', '최근 읽은 도서', '즐겨찾기' 등) 메인 헤더 타이틀 위치에 해당 카테고리 이름이 시원하고 직관적으로 바로 출력됨을 확인함.
