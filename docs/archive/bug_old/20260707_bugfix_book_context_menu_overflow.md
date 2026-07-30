# 20260707_bugfix_book_context_menu_overflow.md

---
type: bugfix
date: 2026-07-07
status: resolved
files:
  - static/js/book_context_menu.js
---

## 버그 내역

도서 리스트에서 마우스 우클릭 시 표시되는 컨텍스트 메뉴가 화면(뷰포트) 경계를 벗어나 잘려서 출력되는 문제.

특히 화면 오른쪽 끝이나 하단 가장자리에 위치한 도서 카드를 우클릭할 때 메뉴 항목이 화면 밖에 렌더링되어 클릭할 수 없는 상태가 발생.

## 영향도

- **영향 범위**: 도서 리스트 그리드 뷰 및 상세 뷰의 단행본 카드 우클릭 메뉴 전체
- **심각도**: 중간 (메뉴 항목 접근 불가로 기능 사용 불가)
- **재현 조건**: 화면 우측 또는 하단 가장자리에 위치한 도서 카드에서 우클릭

## 원인 분석

`book_context_menu.js`의 `showBookContextMenu()` 함수에서 메뉴 위치를 마우스 클릭 좌표(`clientX`, `clientY`)에 기반하여 설정할 때 **뷰포트 경계 체크 로직이 없었음**.

반면, 동일 프로젝트의 `category.js` `showContextMenu()` 함수에는 이미 경계 체크 로직이 구현되어 있었으나, 도서 컨텍스트 메뉴에는 적용되지 않은 상태였음.

## 수정사항

### `static/js/book_context_menu.js`

`showBookContextMenu()` 함수에 뷰포트 경계 체크 로직 추가:

1. 메뉴를 먼저 `display: block`으로 표시하여 실제 크기(`offsetHeight`, `offsetWidth`)를 측정
2. 메뉴가 뷰포트 하단을 넘으면 위쪽으로 펼치도록 Y 좌표 보정
3. 메뉴가 뷰포트 우측을 넘으면 왼쪽으로 펼치도록 X 좌표 보정
4. 보정 결과가 음수가 되지 않도록 최소값 보정 적용

## 해결 확인

- 화면 우측/하단 가장자리 도서 카드에서 우클릭 시 메뉴가 뷰포트 내에서 정상 출력됨
- `category.js`의 `showContextMenu()`와 동일한 경계 체크 패턴을 적용하여 일관성 확보
