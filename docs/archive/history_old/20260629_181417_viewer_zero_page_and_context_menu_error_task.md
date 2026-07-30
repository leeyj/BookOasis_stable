---
title: Task - viewer_zero_page_and_context_menu_error
project: BookOasis
category: history
date: 2026-06-29
type: task
---
# 작업 목록 (Task List)

- [x] HTML 템플릿 내 로고의 drop-shadow 필터 옵션 제거
    - [x] `templates/login.html` 내 `filter: drop-shadow(...)` 스타일 제거
    - [x] `database.py`에서 DB_POOL_SIZE 기본값(10) 및 최대 범위(30) 수정
- [x] `library_settings.html`에서 max="30", value="10"으로 입력 폼 제한 변경
- [x] `general.js`에서 UI 기본 대체값을 '10'으로 수정
- [x] `./docs/bug/` 디렉토리에 버그 수정 문서 작성 및 `workflow.md` 업데이트
- [x] `collect_docs.py` 스크립트를 사용하여 전역 문서 동기화 실행
- [x] 변경 사항 동작 확인 및 검증작성
    - [x] `docs/bug/20260629_improvement_logo_neon_glow_remove.md` 작성
    - [x] 수집기 실행
- [x] `walkthrough.md` 작성
