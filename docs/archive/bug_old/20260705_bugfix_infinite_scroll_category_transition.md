---
title: "[버그수정] 카테고리 전환 시 무한 스크롤(옵저버)이 작동하지 않는 결함 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-05
tags: [infinite-scroll, observer, category-transition, frontend, bugfix]
---

# 🐛 카테고리 전환 시 무한 스크롤(옵저버)이 작동하지 않는 결함 조치

이전 카테고리에서 도서를 끝까지 불러와 스피너가 비활성화(`display: none`)된 이후, 다른 카테고리로 전환하여 도서 목록 스크롤을 시도할 때 하단에 무한 로딩 상태만 유지되고 추가 페이지 로딩이 작동하지 않는 결함을 수정했습니다.

---

## 1. 버그 내역 및 현상
* **문제 상황**:
  1. 어떤 카테고리에서 스크롤을 끝까지 내려 `state.hasMore = false`가 되면 스피너가 숨김 처리(`display: none`)됩니다.
  2. 이 상태에서 다른 카테고리를 선택하면, 새로운 도서 렌더링이 이루어지기 전에 사이드바 전환 핸들러(`selectCategory`)가 실행되며 동기식으로 무한 스크롤 옵저버(`initInfiniteScrollObserver()`)를 바인딩해버립니다.
  3. 감시 시작 시점(`observe(spinner)`)에 스피너가 아직 `display: none` 상태에 머물러 있어 브라우저가 교차(Intersection) 감지를 누락하거나 비정상적인 상태로 유지합니다.
  4. 이후 첫 페이지 API 통신이 뒤늦게 완료되어 스피너를 `block`으로 켜고 스크롤을 끝까지 내려도, 옵저버가 교차 상태 변화를 감지하지 못해 두 번째 페이지 데이터가 호출되지 않고 하단 스피너 렉이 유지되는 결함이 나타납니다.

* **원인**:
  - [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js) 내 `selectCategory` 마지막 줄에서 비동기 도서 데이터 통신(`loadBooksList(false)`)이 완료되어 스피너 `display` 속성이 최적화되기 전, 동기식으로 먼저 옵저버 바인딩을 기동하여 옵저버가 먹통이 되는 타임 얼라인(Time Align) 불일치 문제.

---

## 2. 해결 방안 및 수정 사항
1. **옵저버 바인딩 시점을 렌더링 완료 이후로 이관**:
   - [book_list.js](file:///c:/project/media_server/static/js/book_list.js) 상단에 `initInfiniteScrollObserver` 모듈 임포트를 추가했습니다.
   - `loadBooksList` 비동기 함수 맨 마지막 줄(스피너의 최종 `display`가 결정 및 반영된 시점)에 `initInfiniteScrollObserver()`를 호출하게 변경하여, 물리적으로 이미 렌더링이 보장된 스피너 상태에서 감시를 시작하도록 순서를 정밀 조정했습니다.
2. **사이드바 동기식 중복 호출 제거**:
   - [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)의 `selectCategory`에서 API 요청 전에 동기식으로 호출되던 중복 옵저버 바인딩을 소거하여 이중 호출 및 오작동 가능성을 차단했습니다.

---

## 3. 영향도 및 결과
* 이제 이전에 끝까지 스크롤하여 스피너가 소거된 상태에서 어떠한 카테고리로 전환하더라도, 데이터 로딩이 완료된 후 정확하게 스피너를 다시 감시하게 됩니다. 이에 따라 스크롤 시 정상적으로 두 번째 페이지 이후의 청크가 끊김 없이 실시간 로드됩니다.
