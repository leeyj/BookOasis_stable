# 버그 내역 및 해결 사항: EPUB 뷰어 우측 텍스트 잘림 현상 수정

## 버그 내역 (Bug Description)
EPUB 뷰어에서 텍스트를 열었을 때, 왼쪽에는 여백이 존재하지만 오른쪽 글자가 화면 밖으로 벗어나 잘려서 보이는 현상이 보고되었습니다.

## 영향도 (Impact)
- 텍스트 일부가 화면 밖으로 밀려나가기 때문에 문장을 끝까지 읽을 수 없어 심각한 가독성 저하를 유발했습니다.
- 스크롤 모드에서는 컨테이너의 너비(`width: 100%`)와 패딩(`padding: 40px 20px`)이 중첩되어 전체 너비가 100%를 초과하는 현상이 있었고, 페이지 모드에서는 EPUB 자체 렌더러(epub.js)가 생성하는 기본 body 마진/패딩 값이 제어되지 않아 레이아웃이 어긋났습니다.

## 수정 사항 (Modifications)
- **수정된 파일**: `static/js/viewer/epub/scroll_mode.js`, `static/js/viewer/epub/styles.js`
- **구현 방식**: 
  - `scroll_mode.js`: `contentEl`에 `box-sizing: border-box;` 속성을 추가하여 패딩이 요소의 전체 너비(`100%`) 내에 포함되도록 강제했습니다.
  - `styles.js`: `applyRenditionTheme()` 함수에서 `body` 태그에 테마를 주입할 때 `margin: 0 !important`, `padding: 0 !important`, `box-sizing: border-box` 스타일 규칙을 명시적으로 추가하여 epub.js 기본 스타일의 간섭을 차단했습니다.

## 해결 사항 (Resolution)
패딩과 마진이 뷰포트 크기를 초과하지 않도록 보정되어, 페이지 모드 및 스크롤 모드 모두에서 텍스트가 화면 우측을 넘어가지 않고 양옆 여백이 균형 있게 표시되도록 수정되었습니다.
