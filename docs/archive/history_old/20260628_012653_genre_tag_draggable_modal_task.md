---
title: Task - genre_tag_draggable_modal
project: BookOasis
category: history
date: 2026-06-28
type: task
---
# 작업 계획 (Task)

- [x] UI 레이아웃 설계 및 변경 (HTML/CSS)
  - [x] `tab_media_library.html`에서 기존 고정형 플로팅 팝업 제거
  - [x] 드래그가 가능한 헤더를 포함한 장르/태그 플로팅 모달 구조 정의
  - [x] 모달의 드래그 핸들 마우스 커서 스타일 및 보더라인 CSS 정의
- [x] JavaScript 드래그 이동 및 제어 기능 구현 (`genre_tag_filter.js`)
  - [x] 마우스 휠 스크롤 및 개별 이동을 보장하는 `makeDraggable` 함수 구현
  - [x] 최초 트리거 클릭 시 마우스 근처에 모달을 노출하고 헤더 드래그 기능 적용
  - [x] 닫기(X) 버튼을 통해 모달을 닫는 `closeFilterModal` 전역 함수 구현
- [x] 최종 검증 및 아카이빙
  - [x] E2E 동작 검증 및 walkthrough.md 갱신
  - [x] `collect_docs.py` 실행 및 배포
