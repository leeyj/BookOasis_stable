---
title: "모바일 뷰 도서 상세리스트 하단 영역 가려짐 버그 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, mobile, css, layout, view-height, safe-area]
---

# 🐛 모바일 뷰 도서 상세리스트 하단 영역 가려짐 버그 수정

## 1. 버그 내역 및 증상
- 모바일 브라우저 환경에서 도서 상세리스트를 조회할 때, 브라우저 하단 네비게이션 바 및 가상 버튼 영역에 가려져 리스트 맨 아래 영역(단행본 목록 및 이어서 읽기 버튼 등)이 보이지 않고 스크롤을 끝까지 내려도 접근하기 어려운 현상입니다.

## 2. 원인 분석
- **부정확한 100vh 사용**: 메인 레이아웃 wrapper(`div`)가 인라인 스타일을 통해 `100vh` 높이를 기준으로 레이아웃 크기가 고정되어 있었으며, `body`에 지정된 `overflow: hidden` 구조로 인해 브라우저의 bottom address bar 및 navigation bar 크기가 감안되지 않아 하단 영역이 화면 바깥으로 밀려 가려졌습니다.
- **안전 여백(Safe Area) 및 패딩 부족**: 모바일 뷰에서 단행본 목록 하단에 스크롤 가능한 공간(padding-bottom)이 충분히 마련되어 있지 않아 가상 버튼 영역과의 간섭 현상이 발생했습니다.

## 3. 조치 사항
- **[templates/index.html](file:///c:/project/media_server/templates/index.html)**:
  - 인라인 스타일로 고정되었던 레이아웃 속성을 제거하고 `.main-wrapper` 클래스를 분리하여 부여했습니다.
- **[static/css/style.css](file:///c:/project/media_server/static/css/style.css)**:
  - 기본 데스크톱 환경의 `.main-wrapper` 크기 및 백그라운드 필터 설정을 정의했습니다.
- **[static/css/mobile.css](file:///c:/project/media_server/static/css/mobile.css)**:
  - 모바일 해상도(1200px 이하)에서 `.main-wrapper` 높이를 동적 뷰포트 높이(`100dvh`)로 명시하고, safe-area 여백(`env(safe-area-inset-bottom)`)을 감안하여 컨테이너가 뷰포트 안으로 항상 안전하게 정렬되도록 조정했습니다.
  - `.library-main-content` 및 `#book-detail-view`에 하단 여백(`padding-bottom`)을 확보하여 스크롤 시 마지막 요소가 네비게이션 바에 방해받지 않고 화면에 온전히 노출되도록 조치했습니다.

## 4. 해결 확인 및 영향도
- 모바일 뷰포트 범위 내에서 컨테이너의 크기가 적절히 제한되며, 스크롤을 맨 아래로 내렸을 때 단행본 목록 카드 및 버튼들이 겹치거나 가려짐 없이 미려하고 쾌적하게 렌더링됩니다.
