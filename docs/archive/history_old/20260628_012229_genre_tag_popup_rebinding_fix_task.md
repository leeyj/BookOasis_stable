---
title: Task - genre_tag_popup_rebinding_fix
project: BookOasis
category: history
date: 2026-06-28
type: task
---
# 작업 계획 (Task)

- [x] 동적 DOM 갱신 대응 이벤트 바인딩 버그 수정 (`genre_tag_filter.js`)
  - [x] `popupInitialized` 전역 가드 제거
  - [x] 트리거 요소의 `dataset.popupBound` 플래그를 이용해 인스턴스별 바인딩 보장
  - [x] `document` 클릭 이벤트 리스너 중복 바인딩 방지 가드 적용
- [x] 최종 검증 및 아카이빙
  - [x] E2E 동작 검증 및 walkthrough.md 갱신
  - [x] `collect_docs.py` 실행 및 배포
