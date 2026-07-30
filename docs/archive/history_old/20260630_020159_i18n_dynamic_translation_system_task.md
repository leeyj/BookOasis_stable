---
title: Task - i18n_dynamic_translation_system
project: BookOasis
category: history
date: 2026-06-30
type: task
---
# 작업 목록 (Task List)

- [x] HTML 템플릿 내 로고의 drop-shadow 필터 옵션 제거
    - [x] `templates/login.html` 내 `filter: drop-shadow(...)` 스타일 제거
    - [x] `services/book_detail_service.py` 내 `get_media_detail`에서 total_pages=0 일 때의 실시간 파일 카운트 Fallback 로직 추가
- [x] `static/js/book_context_menu.js` 내 `showBookContextMenu` 함수를 window 객체에 전역 바인딩
- [x] `static/js/detail_render.js` 내 oncontextmenu 인라인 호출 인수 공백 오타 수정 (`' true'` -> `true`)
- [x] `api/cache.py` 내 `clean_up_if_needed`에서 `.tmp` 확장자를 가진 파일도 LRU 정리 대상에서 스킵 처리
- [x] `database.py` 내 커넥션 초기화 시 `PRAGMA synchronous = NORMAL;` 적용
- [x] `services/stream_service.py` 내 `record_progress`에서 완독 기준(95% 이상)을 ZIP을 포함하여 일괄 완화 적용
- [x] `static/js/viewer_progress.js` 내 `flushProgress` 함수가 Promise를 반환하도록 수정
- [x] `static/js/viewer.js` 내 `closeMediaViewer`에 progress flush 완료 후 활성 화면 갱신(대시보드, 읽기 목록, 상세 뷰) 로직 탑재
- [x] `./docs/bug/` 디렉토리에 버그 수정 문서 작성 및 `workflow.md` 업데이트
- [x] `collect_docs.py` 스크립트를 사용하여 전역 문서 동기화 실행
- [x] 뷰어 탈출 시 실시간 화면 리렌더링 및 이력 정화 수동 검증및 우클릭 기능 최종 검증작성
    - [x] `docs/bug/20260629_improvement_logo_neon_glow_remove.md` 작성
    - [x] 수집기 실행
- [x] 스캔 중 웹 로드 병목 개선 여부 최종 검증및 우클릭 기능 최종 검증작성
- [x] `walkthrough.md` 작성
- [x] `tools/migrator.py` 내 CLI 인터랙티브 대화형 프롬프트 구현
- [x] 1번 메뉴: Kavita to BookOasis 커버 이미지 표준 WebP 변환 및 리네이밍 탑재
- [x] 2번 메뉴: BookOasis to BookOasis 경로 변경에 따른 DB 갱신 및 물리 커버 해시 리네이밍 구현
- [x] `./docs/history/` 디렉토리에 마이그레이터 고도화 이력 추가 및 `workflow.md` 업데이트
- [x] CLI 인터랙티브 마이그레이터 이관 동작 수동 검증및 우클릭 기능 최종 검증작성
