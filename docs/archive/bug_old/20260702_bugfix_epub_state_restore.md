---
type: bugfix
date: "2026-07-02"
author: Antigravity
title: "EPUB 뷰어 페이지 위치 복원 불가 및 오버레이 페이지 번호 표기 버그 수정"
---

# EPUB 뷰어 페이지 위치 복원 불가 및 오버레이 페이지 번호 표기 버그 수정

## 1. 버그 내역 (Bug Description)
- **증상 1 (위치 복원 불가):** 사용자가 EPUB 도서를 읽다가 나간 뒤 다시 접속하면, 이전까지 읽었던 위치(페이지)가 저장되지 않고 무조건 처음 페이지(0%)부터 다시 열리는 문제가 발생.
- **증상 2 (페이지 번호 오류):** 이전 패치에서 수정 시도에도 불구하고 오버레이 메뉴를 열 때나 뷰어 진입 시 하단의 페이지 상태 표시줄에 여전히 `1/?` 형태의 잘못된 페이지 번호가 노출되는 문제가 존재.
- **영향도:** 사용자가 긴 소설 등 EPUB 도서를 읽을 때 이어보기가 불가능하여 독서 경험을 크게 훼손.

## 2. 원인 분석 (Root Cause Analysis)
- **위치 복원 누락:** `viewer.js`의 `openReader` 함수에서 `initEpubViewer` 호출 시, DB에 저장된 읽은 퍼센트 값(`pagesRead`)을 넘겨주지 않고 누락하여 항상 처음부터 로드되도록 되어 있었습니다.
- **포맷 변수 혼동:** 이전 수정 시 오버레이의 페이지 계산 로직인 `renderer.js`의 `updatePageInfo()` 함수에 `state.activeFormat === 'epub'` 예외 조건을 넣었으나, `viewer.js`에서는 해당 변수를 `state.currentViewerFormat` 이름으로 저장하고 있어 조건문이 작동하지 않았습니다.

## 3. 해결 사항 (Resolution)
- **위치 복원 전달:** `viewer.js`에서 `initEpubViewer(bookId, pagesRead, totalPages)` 파라미터로 `pagesRead`를 정상 전달하도록 수정했습니다.
- **EPUB 퍼센트 복구 처리:** `viewer_epub.js`에서 `epubBook.locations.generate()`가 완료된 직후, `pagesRead` 값이 존재할 경우 해당 퍼센트를 cfi로 역계산(`cfiFromPercentage`)하여 `epubRendition.display(cfi)`로 저장된 위치로 곧바로 점프하도록 변경했습니다.
- **변수 오타 수정:** `renderer.js`의 `updatePageInfo()` 함수 내 조건문을 `state.currentViewerFormat === 'epub'`로 정정하여, 메뉴창을 열 때마다 `1/?` 로 글자가 깨지던 문제를 완벽히 해결했습니다.

## 4. 변경된 파일 목록
- `static/js/viewer.js`
- `static/js/viewer_epub.js`
- `static/js/viewer/renderer.js`
