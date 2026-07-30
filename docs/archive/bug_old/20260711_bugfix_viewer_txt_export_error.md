---
title: "텍스트 뷰어 컴포넌트화 후 nextTxtPage/prevTxtPage export 누락 수정"
project: "BookOasis"
category: "bug"
date: 2026-07-11
tags: [bug, viewer, txt, export]
---

# 텍스트 뷰어 컴포넌트화 후 nextTxtPage/prevTxtPage export 누락 수정

## 1. 버그 내역 (Bug Report)
- **현상**: 1) `viewer_txt.js` 파일 컴포넌트화 리팩토링 후, `viewer.js` 로드 시 `Uncaught SyntaxError: The requested module './viewer_txt.js' does not provide an export named 'nextTxtPage'` 및 `txtJumpToFirstPage` 오류 발생. 2) 다음 페이지로 넘어갈 때 클릭 이벤트는 감지되나 화면이 갱신되지 않고 제자리에 머무는 결함 발생.
- **원인**:
  1. `viewer_txt.js`에서 페이지 이동 및 탐색 기능을 처리하는 `prevTxtPage`, `nextTxtPage`, `txtJumpToFirstPage`, `txtJumpToLastPage` 함수를 `viewer/txt_navigation.js`에서 가져왔으나, 이를 외부 모듈(`viewer.js`)에서 직접 사용할 수 있도록 다시 `export`하는 구문이 누락됨.
  2. `txt_navigation.js`와 `txt_renderer.js` 간에 함수(`renderCurrentChunk`와 `updateTxtSeekBar`)를 상호 직접 import하면서 **순환 참조 (Circular Dependency)**가 발생함. 이로 인해 브라우저 모듈 평가 시점에 함수 바인딩이 깨져 렌더링이 정상 기동되지 못함.

## 2. 영향도 (Impact)
- **대상**: 텍스트(TXT) 리더 및 EPUB 뷰어 전체 화면
- **상세**: 자바스크립트 로드 시 구문 에러로 인한 로딩 실패, 또는 페이지 내비게이션 조작 시 내부 렌더러 루프 차단으로 인한 먹통 결함.

## 3. 수정 사항 (Resolution)
- **수정 소스 파일**:
  - `C:\project\media_server\static\js\viewer_txt.js`
  - `C:\project\media_server\static\js\viewer\txt_position.js`
  - `C:\project\media_server\static\js\viewer\txt_navigation.js`
  - `C:\project\media_server\static\js\viewer\txt_renderer.js`
- **조치 사항**:
  - `viewer_txt.js`에 외부 모듈용 누락 export를 완비했습니다.
  - 서브 컴포넌트 간의 상호 직접 import를 금지하고, 메인 모듈인 `viewer_txt.js`에 브릿지 export 구문을 두어 각 서브 모듈이 메인을 경유해서만 타 모듈 기능을 호출하도록 변경하여 순환 참조를 근본적으로 해소했습니다.
