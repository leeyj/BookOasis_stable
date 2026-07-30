---
title: Task - genre_tag_popup_overflow_fix
project: BookOasis
category: history
date: 2026-06-28
type: task
---
# 작업 계획 (Task)

- [x] 사이드바 스크롤 영역 외부로 팝업 모달 이동 및 fixed 포지셔닝 구현
  - [x] `tab_media_library.html`에서 팝업을 `.library-sidebar` 외부로 배치하여 잘림 방지
  - [x] `genre_tag_filter.js`에서 트리거의 `getBoundingClientRect()`를 활용해 동적 fixed 좌표 설정
  - [x] 사이드바 내부 스크롤 이벤트 감지 시 활성화된 모든 팝업을 즉각 닫도록 최적화
- [x] 최종 검증 및 아카이빙
  - [x] E2E 동작 검증 및 walkthrough.md 갱신
  - [x] `collect_docs.py` 실행 및 배포
