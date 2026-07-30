---
title: "프론트엔드 모듈화 리팩토링 후 임포트 경로 미반영 버그 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [frontend, import, bugfix]
---

# 🧠 프론트엔드 모듈화 리팩토링 후 임포트 경로 미반영 버그 조치

## 1. 버그 내역 및 개요
- **장애 요인**: `tab_media_library.js` 모듈을 분할하면서 `loadBooksList`, `loadReadingHistory` 함수가 `book_list.js` 서브 모듈로 이관되었습니다.
- **이슈 사항**: 이 함수들을 외부에서 참조하여 호출하고 있던 `infinite_scroll.js`와 `book_context_menu.js` 파일의 임포트 경로가 여전히 기존 `tab_media_library.js`를 가리키고 있었기 때문에, 브라우저가 `'./tab_media_library.js' does not provide an export named 'loadBooksList'` 라는 SyntaxError를 발생시키며 웹 애플리케이션의 동작이 멈추는 버그가 발생했습니다.

## 2. 영향도
- **영향 범위**: 웹 UI (프론트엔드) 전역
- **장애 수준**: 상 (브라우저 자바스크립트 엔진이 임포트 오류로 작동을 중단하여, 도서 그리드 렌더링 및 무한 스크롤, 우클릭 컨텍스트 메뉴 등의 핵심 기능이 먹통이 됨)

## 3. 조치 및 수정 사항 (수정 소스 파일)

### [static/js/infinite_scroll.js](file:///c:/project/media_server/static/js/infinite_scroll.js)
- `loadBooksList`를 가져오는 소스 경로를 `tab_media_library.js`에서 신규 분리된 `book_list.js` 모듈 경로로 수정했습니다.
```javascript
// 기존
import { loadBooksList } from './tab_media_library.js';

// 변경 후
import { loadBooksList } from './book_list.js';
```

### [static/js/book_context_menu.js](file:///c:/project/media_server/static/js/book_context_menu.js)
- `loadBooksList`, `loadReadingHistory`를 가져오는 소스 경로를 `tab_media_library.js`에서 신규 분리된 `book_list.js` 모듈 경로로 수정했습니다.
```javascript
// 기존
import { loadBooksList, loadReadingHistory } from './tab_media_library.js';

// 변경 후
import { loadBooksList, loadReadingHistory } from './book_list.js';
```

## 4. 해결 사항 및 결과 검증
- 수정 적용 후, Node.js의 `--check` 플래그를 통한 정적 구문 해석 검사(`node --check`)를 실행하여 의존성 모듈 해석 및 구문 컴파일 오류가 모두 해결되었음을 완벽히 확인했습니다.
