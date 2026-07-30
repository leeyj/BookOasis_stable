---
title: "중간 해상도 환경설정 탭 버튼 레이아웃 깨짐 버그 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, layout, css, settings, flexbox]
---

# 🐛 중간 해상도 환경설정 탭 버튼 레이아웃 깨짐 버그 수정

## 1. 버그 내역 및 증상
- 데스크톱과 모바일 중간급 해상도(태블릿 화면 또는 중간 크기의 창 해상도)에서 환경설정 화면 접근 시, 상단 탭 버튼들이 극도로 수축되며 버튼 내 다국어 텍스트가 한 글자 혹은 두 글자 단위로 세로 정렬(줄 바꿈)되어 깨지고 뒤틀려 출력되는 현상입니다.

## 2. 원인 분석
- **부적절한 flex-wrap 누락**: 탭 네비게이션 컨테이너(`.settings-tabs`)가 인라인 스타일에 의해 `display: flex`만 지정되어 있었으며 기본값인 `flex-wrap: nowrap`으로 적용되었습니다. 모바일 전용 CSS의 가로 스크롤 미디어 쿼리가 적용되지 않는 해상도에서 버튼 수가 많아지자, 남는 영역이 모자라 탭 버튼이 비정상적으로 수축했습니다.
- **flex-shrink 및 white-space 명세 누락**: 개별 탭 버튼(`.settings-tab-btn`) 내 텍스트에 `white-space: nowrap`과 `flex-shrink: 0` 속성이 지정되어 있지 않아 브라우저가 강제로 너비를 축소시키며 텍스트를 줄 바꿈 처리하였습니다.

## 3. 조치 사항
- **[templates/components/views/library_settings.html](file:///c:/project/media_server/templates/components/views/library_settings.html)**:
  - 탭 컨테이너의 인라인 스타일을 완전 제거하고 `.settings-tabs` 클래스로 레이아웃 제어를 이관했습니다.
- **[static/css/style.css](file:///c:/project/media_server/static/css/style.css)**:
  - `.settings-tabs` 스타일 규칙을 신규 선언하고, 데스크톱/중간 해상도 환경에서 탭이 찌그러지는 대신 아래 행으로 부드럽게 감겨 내리도록 `flex-wrap: wrap`을 부여했습니다.
  - `.settings-tab-btn` 내부에 `flex-shrink: 0` 및 `white-space: nowrap`을 명시하여 화면 해상도 변화나 탭 개수 증가 상황에서도 탭 모양과 글자가 온전한 비율을 유지하도록 개선했습니다.
- **[static/css/mobile.css](file:///c:/project/media_server/static/css/mobile.css)**:
  - 모바일(1200px 이하) 환경에서는 줄 바꿈 대신 본연의 가로 슬라이더(터치 스크롤) 작동을 보장하기 위해 `flex-wrap: nowrap !important` 및 `overflow-x: auto !important`로 명시적 오버라이드 조치를 취했습니다.

## 4. 해결 확인 및 영향도
- 모든 해상도(모니터, 태블릿, 창 크기 축소 상태 등)에서 탭 버튼 내부 글자 깨짐 및 왜곡 현상이 완벽히 해소되었습니다.
