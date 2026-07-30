---
title: "환경설정 스캔 스케줄 및 스캔 예약 대기열 조회 탭 통합"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [improvement, ui, layout, settings, tabs]
---

# ⚙️ 환경설정 스캔 스케줄 및 스캔 예약 대기열 조회 탭 통합

## 1. 개선 내역 및 증상
- 환경설정 화면에 너무 많은 탭 버튼(11개)이 늘어서 있어 해상도가 작을 때 탭 리스트가 심하게 찌그러지거나 복잡하게 표현되는 문제가 있습니다. 특히 성격이 매우 유사한 `스캔 스케줄 설정`과 `스캔 예약 조회 (Queue)`가 2개의 독립 탭으로 분리되어 있어 직관성이 저하되었습니다.

## 2. 해결 방안 및 설계
- **탭 리스트 축소**: `스캔 예약 조회` 탭을 삭제하고 `스캔 스케줄 설정` 탭을 **`스캔 스케줄 & 대기열`** 이라는 이름의 단일 탭으로 병합했습니다.
- **통합 뷰포트 구성**: `스캔 스케줄 & 대기열` 탭 선택 시, 상단부에는 스캔 스케줄 테이블이, 하단부에는 실시간 스캔 예약 대기열(Queue) 상태 조회 테이블이 세로로 결합되어 노출되도록 구성했습니다.
- **인터벌 라이프사이클 처리**: 탭 병합에 따라 JavaScript 컨트롤러를 수정하여, `schedule` 탭이 활성화될 때 대기열 API 5초 주기 자동 갱신 인터벌을 함께 시작하고 다른 탭으로 이동 시 정상 소거되도록 수정했습니다.

## 3. 조치 사항
- **[templates/components/views/library_settings.html](file:///c:/project/media_server/templates/components/views/library_settings.html)**:
  - 탭 버튼 목록에서 '스캔 예약 조회' 버튼을 삭제하고 '스캔 스케줄 설정' 버튼 이름을 '스캔 스케줄 & 대기열'로 병합했습니다.
  - 두 개 템플릿 포함 구조를 `#settings-tab-schedule` ID의 컨테이너 하위로 병합했습니다.
- **[templates/components/settings/schedule_tab.html](file:///c:/project/media_server/templates/components/settings/schedule_tab.html) & [queue_tab.html](file:///c:/project/media_server/templates/components/settings/queue_tab.html)**:
  - 개별 템플릿 파일들의 최외곽 탭 전용 div(`.settings-tab-content`)를 제거하여, 마크업 조립 시 CSS 충돌이나 중복을 방지했습니다.
- **[static/i18n/ko.json](file:///c:/project/media_server/static/i18n/ko.json) & [en.json](file:///c:/project/media_server/static/i18n/en.json)**:
  - 번역 리소스의 `settings.tab_schedule` 값을 신규 병합 이름에 맞게 수정했습니다.
- **[static/js/settings_tab.js](file:///c:/project/media_server/static/js/settings_tab.js)**:
  - `switchSettingsTab` 함수 내에서 `schedule` 탭 선택 시 `loadQueueStatus()` 및 5초 주기 자동 리프레시 인터벌 설정 프로세스를 동일하게 수행하고, 탭 이탈 시 인터벌을 해제하도록 라이프사이클을 통일했습니다.

## 4. 해결 확인 및 영향도
- 환경설정 상단 탭의 개수가 10개로 감소해 헤더 부분이 한결 여유롭고 깔끔해졌으며, 사용자가 스케줄 관리와 스캔 대기열 현황을 한 페이지에서 다이렉트로 추적할 수 있어 사용성과 조작 편의성이 크게 상승했습니다.
