---
name: context_menu_unread_0
description: 도서 우클릭 컨텍스트 메뉴에 '읽지 않은 상태로 변경 (0%)' 기능 추가
---

# 🛠️ [기능추가] 도서 우클릭 컨텍스트 메뉴 내 '읽지 않은 상태로 변경 (0%)' 기능 개발

도서 목록이나 대시보드에서 도서 카드 우클릭 시 호출되는 컨텍스트 메뉴에 '읽지 않은 상태로 변경 (0%)' 항목을 새로 신설하여, 읽던 도서의 진척도를 즉시 0%로 초기화하고 최근 읽은 도서 목록에서 제외할 수 있는 사용성 편의를 개발했습니다.

## 1. 개요 및 비즈니스 로직
* **현상 및 요구사항**: 사용자가 책을 읽다가 중간에 중단하거나 초기화하여 '최근 읽은 도서' 섹션에서 빼고 싶을 때, 강제로 진행률을 0%로 원복시키는 기능이 부재했습니다.
* **해결 방안**: 
  - 백엔드에 `/api/media/unread` API를 개설하여, 지정한 `book_id`에 속한 진행 상태(`user_progress` 및 `user_reading_log` 통계) 레코드를 `DELETE` 구문으로 완전히 소거시킵니다.
  - 이를 통해 책의 독서 기록 자체가 깨끗이 삭제되므로 자연스럽게 '최근 읽은 도서(History / pages_read > 0)' 필터링 조건에서 탈락되어 소거됩니다.
  - 프론트엔드에서는 우클릭 후 해당 버튼을 탭하면 API 성공 후 현재 위치한 화면(대시보드, 최근 읽은 도서 리스트, 도서 상세 모달 등)을 동적으로 갱신(리로드)하여 유저에게 즉각적이고 직관적인 변화를 제공합니다.

## 2. 세부 조치 내용
1. **백엔드 라우트 추가 ([api/stream.py](file:///c:/project/media_server/api/stream.py))**:
   * `@stream_bp.route('/api/media/unread', methods=['POST'])` 엔드포인트를 추가하고, 로그인된 유저의 `user_id`와 요청받은 `book_id`를 기반으로 `user_progress` 및 `user_reading_log`에서 매칭 행을 소거하도록 SQLite 트랜잭션을 구현했습니다.
2. **프론트엔드 API 구현 ([static/js/api.js](file:///c:/project/media_server/static/js/api.js))**:
   * `markBookAsUnread(type, bookId)` 메소드를 추가해 JSON POST 인터페이스를 연동했습니다.
3. **HTML 요소 갱신 ([templates/components/context_menus.html](file:///c:/project/media_server/templates/components/context_menus.html))**:
   * `#book-context-menu` 내부에 `triggerMarkAsUnread()`를 연동한 `ctx-unread-book` 리스트 아이템을 배치했습니다.
4. **JS 제어 및 리프레시 구현 ([static/js/book_context_menu.js](file:///c:/project/media_server/static/js/book_context_menu.js) & [static/js/tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js))**:
   * `triggerMarkAsUnreadAction()` 동작 함수를 통해 API 호출 후 성공 시 홈 대시보드(`loadDashboardData`), 최근 목록(`loadReadingHistory`), 도서 상세 목록(`openBookDetail` / `loadBooksList`)을 자동 연쇄 리로드하도록 트리거를 조율했습니다.
5. **다국어 추가 ([static/i18n/ko.json](file:///c:/project/media_server/static/i18n/ko.json) & [en.json](file:///c:/project/media_server/static/i18n/en.json))**:
   * `context_menu.mark_as_unread` 키를 한국어/영어 번역 리소스에 탑재했습니다.

## 3. 수정 파일 목록
* [api/stream.py](file:///c:/project/media_server/api/stream.py) (라우트 추가)
* [static/js/api.js](file:///c:/project/media_server/static/js/api.js) (API 연동)
* [templates/components/context_menus.html](file:///c:/project/media_server/templates/components/context_menus.html) (HTML 요소 추가)
* [static/js/book_context_menu.js](file:///c:/project/media_server/static/js/book_context_menu.js) (동작 함수 개발)
* [static/js/tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js) (글로벌 윈도우 바인딩)
* [static/i18n/ko.json](file:///c:/project/media_server/static/i18n/ko.json) & [en.json](file:///c:/project/media_server/static/i18n/en.json) (다국어 리소스)
