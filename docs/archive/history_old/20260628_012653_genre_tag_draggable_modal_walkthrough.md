---
title: Walkthrough - genre_tag_draggable_modal
project: BookOasis
category: history
date: 2026-06-28
type: walkthrough
---
# 장르/태그 플로팅 드래그 모달창 개편 결과 (Walkthrough)

## 변경 사항
- **[tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**:
  - 기존의 고정형 플로팅 팝업(`#genre-popup`, `#tag-popup`)을 제거하고, 상단 드래그 핸들 헤더(`.modal-drag-handle`)와 우측 상단 닫기(X) 버튼을 포함한 개별 윈도우 스타일의 모달창 구조(`#genre-modal`, `#tag-modal`)로 개편했습니다.
- **[genre_tag_filter.js](file:///c:/project/media_server/static/js/genre_tag_filter.js)**:
  - 마우스 클릭 및 드래그 변위를 계산해 모달창을 실시간으로 위치 이동시키는 `makeDraggable(element, handle)` 기능을 추가 구현했습니다.
  - 헤더 영역 드래그 시에만 마우스 움직임이 추적되도록 설계하여 목록 내부에서의 스크롤 조작 및 필터 클릭 시의 오작동을 완전히 방어했습니다.
  - 사용자가 "장르" 또는 "태그" 트리거를 클릭하면 초기 위치(트리거의 오른쪽)로 모달이 노출되며, 이후 닫기(X) 버튼을 클릭하거나 장르/태그 항목을 선택하여 필터를 적용할 때만 닫히도록 흐름을 정돈했습니다.

## 수동 검증 방법
1. 브라우저에서 좌측 사이드바 하단의 "장르" 또는 "태그" 버튼을 클릭합니다.
2. 장르/태그 모달창의 상단 헤더 영역(장르 필터/태그 필터 글씨 부분)을 마우스 왼쪽 버튼으로 클릭한 채 드래그하여 화면 전체에 부드럽게 돌아다니는지 검증합니다.
3. 모달창 내에서 마우스 휠을 굴렸을 때 드래그가 끊기거나 이상 동작을 하지 않고 내부 목록만 정상 스크롤 되는지 확인합니다.
4. 모달창 우측 상단의 (X) 아이콘을 눌러 정상적으로 닫히는지 확인하고, 장르/태그 목록 항목을 선택했을 때 필터가 반영되며 모달창이 닫히는지 검증합니다.
