---
title: "모달창이 화면 중앙을 이탈해 스크롤해야만 보이는 CSS Fixed 버그 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-20
tags: [modal, css, viewport, fixed, bugfix]
---

# 모달창이 화면 중앙을 이탈해 스크롤해야만 보이는 CSS Fixed 버그 조치

## 1. 버그 내역 및 현상
- **현상**: 긴 도서 리스트를 아래로 한참 스크롤한 후 "메타정보 검색" 모달창을 띄우면, 모달창이 현재 화면(뷰포트)의 정중앙에 뜨지 않고 문서 최상단 방향으로 올라가 버려, 다시 위로 한참 휠 스크롤해야만 모달을 볼 수 있는 오동작 발생.
- **원인**:
  1. CSS `.library-modal` 클래스가 `position: fixed`로 잘 지정되어 있었으나, 돔 구조상 탭 컨테이너의 하위에 중첩되어 있었음.
  2. 탭 전환이나 슬라이드 레이아웃의 조상 엘리먼트에 `transform` 이나 `filter` 등의 CSS 효과가 적용되어 있을 경우, `fixed` 포지션 기준점이 브라우저 뷰포트(`window`)가 아닌 해당 `transform` 조상 박스로 강제 변경(Containing Block)되는 웹 표준 명세 한계로 인해 발생함.

## 2. 영향도
- **영향**: 모니터 높이보다 문서 스크롤이 길어지는 상황에서 모달창을 기동할 때마다 모달 유실 및 스크롤을 강제 강요하여 사용자 경험(UX)을 심각하게 저해함.

## 3. 수정 사항
- **대상 파일**: [static/js/tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
- **조치 사항**:
  - `DOMContentLoaded` 초기화 함수 내에, 렌더링된 모든 모달창(`.library-modal`) 돔 객체를 검출하여 HTML의 최상위 루트 노드인 `document.body` 최하단으로 강제 전입(`appendChild`)하는 스크립트 헬퍼 추가.
  - 조상 컨테이너의 중첩 영향 및 `transform` 구조적 간섭을 완벽히 차단하여, 브라우저 스크롤 높이와 상관없이 언제나 브라우저 화면의 실시간 정중앙에 모달이 고정 노출되도록 물리적 돔 위치 교정.

## 4. 해결 확인 및 검증
- 원격 배포 후 스크롤 상태에서 모달 재기동 및 뷰포트 고정 여부 검증은 사용자가 직접 홈 서버에서 수행 예정.
