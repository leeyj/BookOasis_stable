---
title: Task - temp_cache_file_eviction
project: BookOasis
category: history
date: 2026-06-29
type: task
---
# 작업 목록 (Task List)

- [x] HTML 템플릿 내 로고의 drop-shadow 필터 옵션 제거
    - [x] `templates/login.html` 내 `filter: drop-shadow(...)` 스타일 제거
    - [x] `services/book_detail_service.py` 내 `get_media_detail`에서 total_pages=0 일 때의 실시간 파일 카운트 Fallback 로직 추가
- [x] `static/js/book_context_menu.js` 내 `showBookContextMenu` 함수를 window 객체에 전역 바인딩
- [x] `static/js/detail_render.js` 내 oncontextmenu 인라인 호출 인수 공백 오타 수정 (`' true'` -> `true`)
- [x] `./docs/bug/` 디렉토리에 버그 수정 문서 작성 및 `workflow.md` 업데이트
- [x] `collect_docs.py` 스크립트를 사용하여 전역 문서 동기화 실행
- [x] 스캔 중 뷰어 기동 및 우클릭 기능 최종 검증작성
    - [x] `docs/bug/20260629_improvement_logo_neon_glow_remove.md` 작성
    - [x] 수집기 실행
- [x] `walkthrough.md` 작성
