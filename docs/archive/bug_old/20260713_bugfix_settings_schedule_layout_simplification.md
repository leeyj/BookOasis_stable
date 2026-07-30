---
title: "환경설정 스캔 스케줄 설정 테이블 간소화 및 작업 컨텍스트 메뉴 통합"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [improvement, ui, layout, settings, context-menu]
---

# ⚙️ 환경설정 스캔 스케줄 설정 테이블 간소화 및 작업 컨텍스트 메뉴 통합

## 1. 개선 내역 및 증상
- 기존 스캔 스케줄 설정 화면에서 한 행에 `저장`, `스캔`, `강제 스캔` 등 너무 많은 버튼과 `최근 스캔 시각` 컬럼이 한번에 출력되어, 해상도가 작거나 중간 크기인 기기에서 레이아웃이 매우 복잡하고 뒤틀려 시각적 가독성이 크게 저하되는 현상입니다.

## 2. 해결 방안 및 설계
- **컬럼 간소화**: 정보량이 많은 `최근 스캔 시각` 컬럼을 테이블 상에서 완전히 제거하여 레이아웃 가로 공간을 확보했습니다.
- **작업 버튼 단일화**: 3개의 개별 액션 버튼(저장, 스캔, 강제 스캔)을 하나의 `작업` 버튼으로 통합하고, 해당 버튼 클릭 시 위치 기반으로 팝업되는 컨텍스트 메뉴를 추가했습니다.
- **컨텍스트 메뉴 헤더 배치**: 제거된 `최근 스캔 시각` 정보를 `작업` 컨텍스트 메뉴 상단의 헤더 영역에 노출함으로써 정보의 손실 없이 간결하고 정돈된 화면을 구현했습니다.

## 3. 조치 사항
- **[templates/components/settings/schedule_tab.html](file:///c:/project/media_server/templates/components/settings/schedule_tab.html)**:
  - 헤더 영역에서 `최근 스캔 시각` `<th>` 요소를 제거하고, 작업 컬럼 폭을 줄였습니다.
- **[templates/components/context_menus.html](file:///c:/project/media_server/templates/components/context_menus.html)**:
  - 스케줄 행 클릭 시 오픈되는 `#schedule-action-context-menu` 마크업을 신규 추가하고, 상단 헤더에 최근 스캔 시각 정보 영역 및 3가지 작업(저장/스캔/강제 스캔) 선택 항목을 배치했습니다.
- **[static/js/scheduler.js](file:///c:/project/media_server/static/js/scheduler.js)**:
  - 테이블 동적 렌더링 시 최근 스캔 시각 TD 요소를 제거하고 단일 `작업` 버튼으로 간소화했습니다.
  - 버튼 클릭 시 타겟 엘리먼트 좌표 기준 뷰포트 내 최적의 위치를 찾아 메뉴를 표시하고, 이벤트를 처리하는 `showScheduleActionMenu(event, libraryId, name, lastScannedAt)` 함수를 바인딩했습니다.
  - 문서 전체 클릭 시 메뉴가 자동으로 닫히도록 클릭 리스너를 구현했습니다.

## 4. 해결 확인 및 영향도
- 스캔 스케줄 설정 탭의 가로 너비 요구사항이 크게 줄어들어 협소한 해상도에서도 뒤틀림 없이 매우 정돈되고 세련된 UI를 제공합니다. 또한 '작업' 메뉴를 통해 직관적으로 상세 명령어들을 수행할 수 있습니다.
