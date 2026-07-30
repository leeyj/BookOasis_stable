---
title: "최근 읽은 도서 무한 로딩 스피너 버그 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-06-23
tags: [bug, ui, reading_history]
---
# 버그 내역
최근 읽은 도서 페이지 하단에 무한 스크롤 로딩 표시(스피너)가 계속 노출되어 사용자에게 로딩 중이라는 오해를 유발하는 문제. 추가로 최근 읽은 도서 표시 개수를 20개에서 30개로 상향 조정 요청.

# 영향도
- 기능은 정상 작동하나 UI 표시 오류로 사용자 경험(UX) 저하 및 오해 유발

# 수정 사항
1. `c:\project\media_server\static\js\book_list.js`
   - `loadReadingHistory()` 함수 내에서 `infinite-scroll-spinner` 요소를 찾아 명시적으로 `display: none` 처리 추가하여 불필요한 스피너 노출 방지.
2. `c:\project\media_server\services\reading_history_service.py`
   - `ReadingHistoryService.get_history()` 메서드 쿼리에서 `LIMIT 20`을 `LIMIT 30`으로 변경하여 최근 읽은 도서 최대 표시 개수 상향.

# 해결 사항
- 최근 읽은 도서 메뉴 진입 시 하단의 로딩 표시가 올바르게 숨김 처리됨.
- 최근 읽은 도서 목록이 최대 30개까지 노출됨.
