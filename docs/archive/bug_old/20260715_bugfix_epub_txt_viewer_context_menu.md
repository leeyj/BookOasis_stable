---
id: bugfix-20260715-epub-txt-viewer-context-menu
date: 2026-07-15
type: bugfix
severity: high
status: fixed
affected_files:
  - static/js/viewer.js
  - static/js/tab_media_library.js
tags: [viewer, epub, txt, context-menu, markAsCompleted, jumpToFirstPage]
---

# 버그 리포트: epub/txt 뷰어 처음으로/완독처리 버튼 미동작

## 버그 내용
EPUB, TXT 뷰어 오버레이 메뉴의 처음으로, 완독처리 버튼이 동작하지 않는 문제.

## 원인 A - 처음으로
viewer.js의 viewerJumpToFirst()에서 epub 분기가 미정의 함수 getEpubModule()을 호출.
epub도 TxtViewer를 사용하므로 txtJumpToFirstPage()를 호출해야 함.

## 원인 B - 완독처리
tab_media_library.js에서 viewer_comic.js의 markAsCompleted로 window.markAsCompleted를 덮어씌움.
comic 버전은 comicTotalPages > 0 조건을 체크하므로 epub/txt에서는 미동작.

## 수정 사항
- static/js/viewer.js: epub 분기를 txtJumpToFirstPage/txtJumpToLastPage 호출로 수정
- static/js/tab_media_library.js: window.markAsCompleted 덮어쓰기 제거
