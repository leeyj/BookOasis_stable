---
title: "자바스크립트 중복 export 구문 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, javascript, syntax-error]
---

# 🐛 자바스크립트 중복 export 구문 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 라이브러리 화면이 기동될 때 웹 브라우저 콘솔에 `Uncaught SyntaxError: Duplicate export of 'initInfiniteScrollObserver'` 오류가 발생하며 전체 스크립트 실행이 중단되는 현상 발생.

## 2. 원인 분석 (Root Cause Analysis)
- `tab_media_library.js`에 `IntersectionObserver` 기능을 추가하면서, 함수 선언 부분에서 `export function initInfiniteScrollObserver`로 내보내기를 지적함과 동시에 파일 제일 하단의 `export { loadLibraries, initInfiniteScrollObserver };` 문에서도 중복으로 내보내기를 지정함.
- ES6 규격 상 한 모듈에서 동일 심볼을 중복 내보내면 브라우저가 정적 구문 해석 단계에서 SyntaxError를 인지하고 스크립트 구동을 전면 중단하게 됨.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
- 파일 최하단 export 구문에서 중복 지정되었던 `initInfiniteScrollObserver`를 제거하고, 원래의 `export { loadLibraries };` 로 단순화하여 문법적 충돌을 해결함.

## 4. 결과 검증 (Verification Results)
- 수정한 소스코드를 원격 홈 서버에 배포하고 서비스를 재기동함. F12 개발자 도구의 콘솔 창에서 SyntaxError가 흔적 없이 소거되고, 무한 스크롤 및 전체 도서관 기능들이 에러 없이 부드럽게 기동됨을 확인함.
