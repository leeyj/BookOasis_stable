---
title: "환경설정 스캔 설정 테이블 입력 폼 모달 통합"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [improvement, ui, layout, settings, modal]
---

# ⚙️ 환경설정 스캔 설정 테이블 입력 폼 모달 통합

## 1. 개선 내역 및 증상
- 기존에는 `Rclone RC 주소`와 `스케줄 주기(Cron식)` 및 `스캔 전 VFS 캐시 새로고침` 체크박스 등의 설정 컨트롤러들이 테이블 행 내에 텍스트 인풋창 형태로 여러 칸에 걸쳐 길게 나열되어 있었습니다.
- 이로 인해 화면 해상도가 작거나 태블릿/모바일 뷰 등 협소한 장치에서 볼 때 테이블 레이아웃이 찌그러지거나 복잡해 보여 시각적 완성도와 사용성을 떨어트렸습니다.

## 2. 해결 방안 및 설계
- **테이블 컬럼 간소화**: 복잡한 입력 폼 컬럼들을 테이블에서 모두 제거하고, 단일 **`설정`** 버튼(기어 아이콘)만 테이블 행에 렌더링하도록 디자인을 간소화했습니다.
- **설정 전용 모달 도입**: `설정` 버튼 클릭 시 해당 카테고리의 Rclone RC 주소, Cron 스케줄 주기, VFS 캐시 새로고침 설정들을 한곳에 깔끔하게 보여주고 수정할 수 있는 모달 `#library-scan-settings-modal`을 신설했습니다.
- **저장 플로우 단순화**: 모달 하단에 배치된 [저장] 버튼을 클릭해 수정 사항을 백엔드로 다이렉트 전송하며, 이에 따라 기존 '작업' 컨텍스트 메뉴의 중복된 '저장' 옵션을 안전하게 제거했습니다.

## 3. 조치 사항
- **[templates/components/settings/schedule_tab.html](file:///c:/project/media_server/templates/components/settings/schedule_tab.html)**:
  - Rclone RC 주소 및 Cron식 스케줄 컬럼 헤더를 소거하고, 대신 `설정` 컬럼 헤더를 신설했습니다.
  - 최신 다크 테마 디자인(유려한 글래스모피즘 및 보라색/그라데이션 강조색)에 맞춘 `#library-scan-settings-modal` 설정 모달 마크업을 추가했습니다.
- **[static/js/scheduler.js](file:///c:/project/media_server/static/js/scheduler.js)**:
  - `loadLibrarySchedules()`에서 렌더링하는 테이블 구조를 5열(카테고리명, 물리 경로, 상태, 설정 버튼, 작업 버튼)로 개편했습니다.
  - `openScanSettingsModal`, `closeScanSettingsModal`, `saveScanSettingsFromModal` 제어 및 API 통신 연동 함수를 새로 구현하고 전역 바인딩을 완료했습니다.
  - `showScheduleActionMenu`에서 기존 '저장' 버튼에 대한 바인딩 코드를 안전하게 배제하고 작동하도록 다듬었습니다.
- **[templates/components/context_menus.html](file:///c:/project/media_server/templates/components/context_menus.html)**:
  - 스캔 작업 컨텍스트 메뉴 목록에서 불필요해진 '저장'(`schedule-action-save`) 리스트 아이템을 삭제했습니다.
- **[static/i18n/ko.json](file:///c:/project/media_server/static/i18n/ko.json) & [en.json](file:///c:/project/media_server/static/i18n/en.json)**:
  - 새 컬럼에 매핑될 다국어 키 `settings.col_config` 번역값을 적용했습니다.

## 4. 해결 확인 및 영향도
- 복잡한 텍스트 입력 칸이 제거되면서 스캔 설정 테이블이 극도로 슬림하고 직관적으로 개편되었습니다. 모달 인터페이스를 통해 복잡한 Rclone 및 스케줄 옵션을 시각적으로 정돈된 공간에서 명확하게 편집할 수 있어, 레이아웃의 완성도 및 안정성을 동시에 확보했습니다.
