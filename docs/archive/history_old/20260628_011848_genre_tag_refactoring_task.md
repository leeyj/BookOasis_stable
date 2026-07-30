---
title: Task - genre_tag_refactoring
project: BookOasis
category: history
date: 2026-06-28
type: task
---
# 작업 계획 (Task)

- [x] UI 레이아웃 설계 및 변경 (HTML/CSS)
  - [x] `tab_media_library.html`에서 기존 스크롤형 `<ul>` 목록 영역 제거
  - [x] "장르"와 "태그" 트리거용 메뉴 아이템 디자인 추가
  - [x] 팝업 모달/컨텍스트 메뉴를 위한 전용 컨테이너 생성 및 CSS 스타일링
- [x] JavaScript 필터 및 이벤트 로직 리팩토링 (`genre_tag_filter.js`)
  - [x] 클릭 시 오른쪽 팝업 모달 표시/숨김 제어 및 포지셔닝 구현
  - [x] 호버 및 외부 클릭 시 팝업 닫기 이벤트 핸들러 구현
  - [x] 동적 장르/태그 로드 후 팝업 내부 목록에 렌더링하도록 변경
  - [x] 항목 클릭 시 필터 적용 및 활성화 상태(CSS class active) 동기화
- [x] 최종 E2E 수동 검증 및 Walkthrough 문서 작성
