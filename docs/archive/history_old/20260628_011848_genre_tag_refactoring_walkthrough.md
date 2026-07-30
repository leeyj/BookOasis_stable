---
title: Walkthrough - genre_tag_refactoring
project: BookOasis
category: history
date: 2026-06-28
type: walkthrough
---
# 장르 및 태그 사이드바 메뉴 리팩토링 검증 결과 (Walkthrough)

## 변경 사항
- **[tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**:
  - 기존 세로 스크롤 방식의 `<ul>` 목록 영역을 제거하였습니다.
  - "장르"와 "태그"를 클릭하여 사이드바 외부 오른쪽에 팝업이 노출되도록 하는 `li.menu-item` 트리거 구조로 변경하였습니다.
  - Glassmorphism 효과(`backdrop-filter`), 부드러운 애니메이션(`transition: opacity/transform`), 깔끔한 그림자(`box-shadow`) 등이 적용된 플로팅 컨텍스트 메뉴 컨테이너(`#genre-popup`, `#tag-popup`)를 구성하였습니다.
- **[genre_tag_filter.js](file:///c:/project/media_server/static/js/genre_tag_filter.js)**:
  - 마우스 호버 시 팝업이 자연스럽게 열리고, 마우스가 트리거와 팝업을 완전히 벗어났을 때 약간의 지연 시간(250ms) 후 서서히 닫히도록 마우스 이벤트를 완벽하게 제어했습니다.
  - 트리거 클릭을 통한 토글(열기/닫기)을 지원하며, 팝업 바깥 빈 곳을 클릭했을 때도 팝업이 닫히도록 문서(document) 단위의 외부 클릭 이벤트 감지 로직을 구현하였습니다.
  - 특정 장르/태그가 활성화되면 트리거 버튼 자체에도 `: 장르명`과 같이 뱃지 형태로 활성화 상태를 표현하며, 활성화 스타일(`.active`)을 즉시 갱신하도록 처리했습니다.

## 수동 검증 방법
1. 브라우저에서 웹 서비스에 접속하여 좌측 사이드바를 확인합니다.
2. "장르" 또는 "태그" 영역 위에 마우스를 올리거나 클릭하면 오른쪽에 팝업 모달이 부드럽게 나타납니다.
3. 팝업 내부에서 마우스 휠 스크롤이 정상 작동함을 확인합니다.
4. 원하는 장르/태그를 클릭하면 필터가 적용되고 팝업이 닫히며, 트리거 텍스트 옆에 `: 선택한장르` 뱃지가 갱신되는 것을 확인합니다.
