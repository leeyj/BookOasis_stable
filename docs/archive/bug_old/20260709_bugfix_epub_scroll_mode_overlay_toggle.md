# 버그 내역 및 해결 사항: EPUB 뷰어 스크롤 모드 오버레이 토글 불가 버그

## 버그 내역 (Bug Description)
EPUB 뷰어를 스크롤 모드(`scroll`)로 사용할 때, 화면 중앙을 터치하여도 뷰어 오버레이 메뉴(컨텍스트 메뉴)가 나타나지 않는 현상이 있었습니다.

## 영향도 (Impact)
- 모바일 및 데스크톱 환경에서 EPUB 도서를 스크롤 모드로 읽을 때, 오버레이 메뉴를 호출할 방법이 없어 사용자 편의성이 크게 떨어졌습니다.
- EPUB iframe 내부에서 발생한 터치 이벤트가 상위 문서(document)로 버블링되지 않음에도 불구하고, 하위 스크립트(`interactions.js`)에서 스크롤 모드일 경우 자체적인 이벤트 처리를 모두 무시하도록 작성되어 있었습니다.

## 수정 사항 (Modifications)
- **수정된 파일**: `static/js/viewer/epub/interactions.js`
- **구현 방식**: 
  - `handleContentTap` 및 `handleRenderAreaTap` 함수 내에 스크롤 모드 판별 분기를 추가했습니다.
  - 기존에는 `scrollMode === 'page'`가 아니면 이벤트를 무시(return)했지만, 스크롤 모드에서도 화면의 중앙 영역(`zone === 'center'`)을 탭했을 경우 `toggleOverlay()`를 호출하도록 수정했습니다.
  - EPUB 내부의 클릭 이벤트 리스너(`click`, `pointerup`)에는 이미 350ms 딜레이를 통한 중복 실행 방지(Double-toggle throttling) 로직이 적용되어 있어, 일반 뷰어에서 겪었던 "메뉴 중복 토글 버그"는 발생하지 않음을 확인했습니다.

## 해결 사항 (Resolution)
EPUB 뷰어의 스크롤 모드에서도 일반 만화 뷰어와 동일하게 화면 중앙을 터치하여 안전하게 뷰어 오버레이 메뉴를 호출하고 닫을 수 있게 되었습니다.
