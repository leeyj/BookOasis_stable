---
title: Walkthrough - genre_tag_popup_overflow_fix
project: BookOasis
category: history
date: 2026-06-28
type: walkthrough
---
# 사이드바 스크롤 외부 팝업 분리 및 잘림 현상 조치 결과 (Walkthrough)

## 변경 사항
- **[tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**:
  - 팝업 요소들(`#genre-popup`, `#tag-popup`)을 `overflow-y: auto`가 선언된 `.library-sidebar` 내부에 두지 않고, 사이드바 외부의 `.media-library-container` 형제 레벨로 이동 배치함으로써 CSS overflow 영역 밖으로 밀려날 때 팝업이 잘리거나 숨겨지는 레이아웃 문제를 완벽하게 해결했습니다.
- **[genre_tag_filter.js](file:///c:/project/media_server/static/js/genre_tag_filter.js)**:
  - 팝업의 위치 지정을 기존 `position: absolute`에서 `position: fixed`로 변경하고, 마우스가 올라가 노출되는 타이밍에 트리거의 `getBoundingClientRect()` 값을 동적으로 계산하여 트리거의 바로 오른쪽에 오차가 없도록 정렬 및 배치했습니다.
  - 사이드바 내에서 휠 스크롤이 발생할 경우, 플로팅 팝업이 허공에 둥둥 뜨거나 위치가 어긋나는 문제를 방지하기 위해 사이드바가 스크롤되면 열려 있는 모든 팝업을 즉시 닫도록 보완했습니다.

## 수동 검증 방법
1. 브라우저에서 사이드바의 "장르" 또는 "태그"를 클릭하거나 호버하여 팝업이 노출되게 합니다.
2. 팝업의 우측면이 잘리지 않고 메인 콘텐츠 영역 위로 완전히 선명하게 오버레이(fixed positioning)되는지 확인합니다.
3. 팝업이 띄워진 상태에서 사이드바 위에서 마우스 휠 스크롤을 시도할 때 팝업이 자연스럽게 닫히는지 검증합니다.
