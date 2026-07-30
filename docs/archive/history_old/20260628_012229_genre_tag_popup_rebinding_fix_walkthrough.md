---
title: Walkthrough - genre_tag_popup_rebinding_fix
project: BookOasis
category: history
date: 2026-06-28
type: walkthrough
---
# 동적 DOM 갱신 시 장르/태그 팝업 이벤트 유실 버그 조치 결과 (Walkthrough)

## 변경 사항
- **[genre_tag_filter.js](file:///c:/project/media_server/static/js/genre_tag_filter.js)**:
  - 탭 스위칭 또는 카테고리 로딩 시 사이드바 DOM이 초기화 및 재생성되면 전역 변수 `popupInitialized` 플래그로 인해 이벤트 리스너가 다시 걸리지 않던 버그를 분석 및 조치했습니다.
  - 새로 생성된 엘리먼트 인스턴스에 직접 `dataset.popupBound = 'true'` 데이터 플래그를 붙여, 개별 엘리먼트 기준으로 이벤트 중복 바인딩을 방지하면서 재생성 시 바인딩이 누락되지 않도록 로직을 수정했습니다.
  - `document` 전체 클릭 외부 감지 리스너는 `documentClickBound`를 활용해 전역에 1회만 등록되도록 하여 메모리 누수 및 중복 동작 문제를 완벽하게 예방했습니다.

## 수동 검증 방법
1. 브라우저에서 사이드바의 "장르" 또는 "태그"를 클릭하여 팝업이 노출되는지 확인합니다.
2. 상단의 카테고리(Home, 최근 읽은 도서, 즐겨찾기 등)를 다수 클릭하여 사이드바가 동적으로 갱신되도록 유도합니다.
3. 갱신 후에도 "장르" 및 "태그"를 클릭/호버할 때 팝업 모달이 문제없이 부드럽게 노출되는지 최종 검증합니다.
