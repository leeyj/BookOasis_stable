---
title: Task - opds_and_ui_enhancements
project: BookOasis
category: history
date: 2026-06-25
type: task
---
# OPDS 뷰어 통합 기능 확대 및 웹 UI 상태 관리 개선 작업 목록

## 작업 항목

### A. 웹 UI 리팩토링 및 상태 관리
- `[x]` 로그인 페이지 CSS 분리 (`static/css/login.css` 생성)
- `[x]` 로그인 페이지 JavaScript 분리 (`static/js/login.js` 생성)
- `[x]` 로그인 페이지 HTML 리팩토링 (`templates/login.html` 수정)
- `[x]` 뷰어 뒤로가기 이력 상태 관리 추가 (`static/js/viewer.js`)
- `[x]` 페이지 스크롤 위치 저장/복원 상태 관리 추가 (`static/js/state.js`, `static/js/modal.js`)

### B. OPDS 피드 기본 개선
- `[x]` OPDS XML 생성 시 특수 문자 이스케이핑 및 URL 인코딩 (`api/opds.py`)
- `[x]` OPDS 커버 이미지 MIME 타입 감지 및 동적 반영 (`api/opds.py`)
- `[x]` `/covers` 경로 인증 미적용으로 OPDS 클라이언트에서 커버 접근 가능하도록 개선

### C. OPDS 시리즈 썸네일 표시
- `[x]` `_series_entries()` 함수에서 각 시리즈의 대표 `cover_image` 조회 추가
- `[x]` Navigation 타입 항목에도 `opds:image` 및 `opds:image/thumbnail` 링크 포함

### D. OPDS 신규 추가 및 최근 읽은 섹션 추가
- `[x]` 최상위 피드에 "신규 추가", "최근 읽은" Navigation 항목 추가
- `[x]` `/opds/recently-added` 엔드포인트 구현 (일반)
- `[x]` `/opds/recently-read` 엔드포인트 구현 (일반)
- `[x]` `/opds/adult/recently-added` 엔드포인트 구현 (성인)
- `[x]` `/opds/adult/recently-read` 엔드포인트 구현 (성인)
- `[x]` `_recently_added_entries()` 헬퍼 함수 구현 (DB 직접 조회)
- `[x]` `_recently_read_entries()` 헬퍼 함수 구현 (DB 직접 조회)

### E. 버그 수정 및 검증
- `[x]` 최근 읽은 도서 커버 미표시 문제 해결 (원본 `cover_image` 조회)
- `[x]` Python 문법 검사 및 배포 전 검증 (`python -m py_compile`)
- `[x]` OPDS 피드 XML 규격 검증 및 정상 동작 확인

### F. 문서화
- `[x]` Task 문서 작성 (`docs/history/20260625_024244_opds_and_ui_enhancements_task.md`)
- `[x]` Walkthrough 문서 작성 (`docs/history/20260625_024244_opds_and_ui_enhancements_walkthrough.md`)
- `[x]` Workflow 마스터 파일 업데이트 (`docs/workflow.md`)

---

## 수정된 파일 목록
- `templates/login.html`
- `static/css/login.css` (신규)
- `static/js/login.js` (신규)
- `static/js/viewer.js`
- `static/js/state.js`
- `static/js/modal.js`
- `api/opds.py`
- `api/auth.py`
- `api/stream.py`
