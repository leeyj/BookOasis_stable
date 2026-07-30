---
title: "카테고리 전환 시 스크롤 위치 최상단 리셋 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [bugfix, scroll-reset, category-switch]
---

# 🐛 카테고리 전환 시 스크롤 위치 최상단 리셋 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 보관함 목록 뷰에서 특정 카테고리를 아래쪽까지 스크롤하여 탐색한 이후, 다른 카테고리(예: 즐겨찾기, 만화 등)로 클릭 전환하면 새로 로딩된 화면의 스크롤바 위치가 최상단이 아닌 이전 카테고리에서 스크롤했던 하단 위치에 그대로 머무는 버그 발생.
- 이로 인해 새로운 목록을 정상 탐색하기 위해 매번 수동으로 마우스 휠을 굴려 위로 올라가야 하는 불편이 수반됨.

## 2. 원인 분석 (Root Cause Analysis)
- Single Page Application(SPA) 스타일로 비동기 렌더링 영역(Grid 뷰 등)만 교체하는 구조에서, 브라우저 윈도우(`window`) 객체는 동일하게 유지됨.
- 카테고리나 도서 타입(일반/성인) 탭 전환 시 화면의 데이터는 갱신되지만, 윈도우 스크롤 위치를 복구하는 명시적인 갱신 코드(`window.scrollTo(0, 0)`)가 부재하여 기존 스크롤 위치가 유지되는 고착 오류가 발생함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
  - 카테고리 클릭 핸들러인 `selectCategory(id)`의 진입 시점에 `window.scrollTo(0, 0);` 구문을 적용하여 화면 전환 시 스크롤 위치를 최상단으로 강제 초기화하도록 조치함.
  - 일반/성인 도서 전환을 처리하는 `switchLibraryType(type)` 함수 또한 동일하게 `window.scrollTo(0, 0);` 구문을 주입하여 탭 교체 시 스크롤이 유지되지 않도록 보정함.

## 4. 결과 검증 (Verification Results)
- 소스 코드 적용 후 카테고리나 일반/성인 토글 전환 시, 이전의 스크롤 하강 위치가 깔끔하게 리셋되어 무조건 맨 위 도서 목록부터 노출되는 정상적인 네비게이션 작동을 확인 완료함.
