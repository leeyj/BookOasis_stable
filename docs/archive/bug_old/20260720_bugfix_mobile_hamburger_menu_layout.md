---
id: "20260720_bugfix_mobile_hamburger_menu_layout"
date: 2026-07-20
category: "bugfix"
severity: "medium"
status: "fixed"
tags: [mobile, responsive, sidebar, layout, css, specificity]
---

# 20260720 — 모바일 라이브러리 햄버거 메뉴 레이아웃 개선 완료

## 버그 내역

### 현상
- 모바일 해상도(width 1200px 이하)에서 라이브러리 상단의 햄버거 토글 버튼을 작동하여 메뉴를 열었을 때, 아이콘은 `Xmark`로 바뀌지만 내부 카테고리 목록(`.sidebar-collapsible-content`)이 부서지거나 아래로 펼쳐지지 않아 메뉴 선택이 불가능한 현상 발생.

### 근본 원인
- **마진/패딩 소실**: 접힘 상태(`.sidebar-collapsible-content`)에서 부여한 `margin: 0 !important`, `padding: 0 !important` 속성이 열림 상태(`.show`)에서 원상 복구되지 않고 유지되어 래퍼가 높이를 확보하지 못함.
- **오버플로우 꼬임**: 데스크톱의 사이드바 접힘 상태(`.collapsed`)에 걸려 있는 `overflow: hidden !important` 규칙이 모바일의 `.library-sidebar.collapsed` 스타일에서 완전하게 초기화(visible)되지 못하고 명시도(Specificity) 싸움에서 밀려 자식 요소를 완전히 잘라냈기 때문.

## 영향도
- 모바일 및 태블릿 기기 사용자가 홈, 최근 읽은 도서, 즐겨찾기, 환경설정 탭으로 이동할 수 없는 중대한 모바일 사용성 불편 초래.

## 수정 사항

### 수정 파일 목록

#### `static/css/mobile.css`
- `.library-sidebar.collapsed` 규칙 내부의 `overflow: visible` 속성에 `!important`를 주입하여, 데스크톱의 `overflow: hidden !important` 충돌을 완전 오버라이드.
- `.sidebar-collapsible-content.show` 규칙에 `margin: initial !important` 및 `padding: initial !important` 규칙을 신규 부여하여, 닫힌 상태에서 압착되었던 외부/내부 패딩을 온전하게 기본값으로 복원.
- 안정성 확보를 위해 `max-height: 75vh !important;` 및 `overflow-y: auto !important;` 가중치 보강.

## 해결 사항
- 모바일 및 태블릿 반응형 레이아웃에서 햄버거 버튼 터치 시 사이드바 카테고리가 짓눌리지 않고 부드럽고 미려하게 하단으로 정상 노출 및 세로 스크롤링이 가능함을 검증 완료했습니다.
