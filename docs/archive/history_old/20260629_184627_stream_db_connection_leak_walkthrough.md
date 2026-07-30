---
title: Walkthrough - stream_db_connection_leak
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# Walkthrough: total_pages Fallback 및 우클릭 컨텍스트 메뉴 바인딩 조치 완료

스캔 도중 total_pages가 아직 DB에 갱신되지 않았을 때 만화책 뷰어가 동작하지 않던 현상을 Fallback 코드로 방어하고, 단행본 상세 페이지에서 마우스 우클릭 메뉴가 동작하지 않던 프론트엔드 오류를 수정하였습니다.

## 작업 상세

### 1. total_pages 실시간 Fallback 처리 ([book_detail_service.py](file:///c:/project/media_server/services/book_detail_service.py))
- DB 상에 `total_pages` 필드가 `0` 또는 `None`인 도서의 경우, 파일 포맷이 `zip/cbz`이며 파일이 존재할 때 `get_zip_file_hybrid`를 이용해 실제 이미지 개수를 계산해 채워주도록 방어 처리를 완성하였습니다.
- 이를 통해 신규 등록 중이거나 오프셋 생성이 완료되기 전에 사용자가 책을 열람하더라도 뷰어가 `0`페이지 에러 없이 정상 가동합니다.

### 2. 마우스 우클릭 컨텍스트 메뉴 동작 오류 해결
- **전역 바인딩 누락 조치 ([book_context_menu.js](file:///c:/project/media_server/static/js/book_context_menu.js))**: `showBookContextMenu` 함수를 전역 `window` 객체에 바인딩하여 인라인 `oncontextmenu` 이벤트 핸들러가 참조할 수 있도록 조치하였습니다.
- **문법적 결함 수정 ([detail_render.js](file:///c:/project/media_server/static/js/detail_render.js))**: `oncontextmenu` 태그 속성에서 `showBookContextMenu`를 호출할 때 마지막 인수 내 공백 기입 에러인 `' true'`를 올바른 boolean 표현인 `true`로 수정했습니다.

### 3. 작업 이력 수집 및 문서화
- `./docs/bug/20260629_bugfix_viewer_zero_page_and_context_menu_error.md` 버그 조치 문서를 생성하였습니다.
- `workflow.md` 이력 마스터에 등록하고 `collect_docs.py`를 수행하여 세션 기록 동기화를 완료하였습니다.
