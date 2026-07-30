---
title: "환경설정 사용자 관리 탭 HTML 태그 중첩 및 비대화 버그 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-22
tags: [frontend, html, bugfix]
---

# 🐛 환경설정 사용자 관리 탭 HTML 태그 중첩 및 비대화 버그 조치

## 1. 버그 내역 및 현상
- **현상**: 환경설정의 `사용자 관리` 탭 버튼을 클릭했을 때 화면 하단에 어떠한 테이블이나 사용자 추가 버튼도 렌더링되지 않고 빈 배경만 출력됨.
- **원인**: 
  - `tab_media_library.html` 내에 스캔 에러 리포트 탭(`settings-tab-reports`)과 그 내부의 `dashboard-section` div를 닫는 `</div>` 태그 2개가 누락됨.
  - 이로 인해 바로 아래 정의된 사용자 관리 탭(`settings-tab-users`) 전체가 에러 리포트 탭의 하위 구조로 중첩됨.
  - 에러 리포트 탭이 `display: none`인 상태에서는 사용자 관리 탭 내부의 display가 활성화되어도 브라우저가 요소를 렌더링하지 못함.
  - 또한 단일 `tab_media_library.html` 파일에 모든 모달 및 탭 코드가 전부 하드코딩되어 있어 크기가 ~500라인으로 비대화되었고, 이로 인해 태그 매칭 실수를 유발하기 쉬운 복잡한 구조를 띄고 있었음.

## 2. 영향도
- **영향 범위**: 어드민(Admin)에 의한 독서 사용자 수동 등록 및 목록 확인 불가.
- **영향 등급**: **Medium** (핵심 기능 정상 작동 여부에는 지장이 없으나, 사용자 추가 UI에 직접적인 접근이 차단됨)

## 3. 수정 및 해결 사항
- **수정 소스 파일**: 
  - [tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)
- **컴포넌트 신규 분리**:
  - [reports_tab.html](file:///c:/project/media_server/templates/components/settings/reports_tab.html) [NEW]
  - [users_tab.html](file:///c:/project/media_server/templates/components/settings/users_tab.html) [NEW]
  - [user_modal.html](file:///c:/project/media_server/templates/components/modals/user_modal.html) [NEW]
  - [library_modal.html](file:///c:/project/media_server/templates/components/modals/library_modal.html) [NEW]
  - [metadata_search_modal.html](file:///c:/project/media_server/templates/components/modals/metadata_search_modal.html) [NEW]
  - [context_menus.html](file:///c:/project/media_server/templates/components/context_menus.html) [NEW]
- **조치 사항**:
  - `tab_media_library.html`의 각 탭 콘텐츠와 모달 창들을 서브 템플릿 파일로 완벽히 컴포넌트화하여 격리시킴.
  - `tab_media_library.html`에서 각 분리된 모듈들을 Jinja2 `{% include %}`로 결합하도록 리팩토링함으로써 복잡도를 크게 낮추고 마크업 중첩 꼬임 버그를 근본적으로 예방함.
  - 정상적인 태그 닫기 순서를 보장하여 `settings-tab-users`가 가려지지 않고 독립적으로 노출되도록 함.
