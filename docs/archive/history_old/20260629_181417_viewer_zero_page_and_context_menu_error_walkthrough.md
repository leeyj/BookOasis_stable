---
title: Walkthrough - viewer_zero_page_and_context_menu_error
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# Walkthrough: DB Connection Pool Exhausted 조치 완료

스캔 작업 시 발생하는 DB 커넥션 풀 부족 장애에 대응하기 위하여, 기본 커넥션 풀 크기를 상향 조정하고 최대 한계를 확장하였습니다.

## 작업 상세

### 1. DB 설정 수정 (`database.py`)
- `_get_pool_size_raw` 함수 내에서 최소/최대 커넥션 풀 크기의 범위를 1~20개에서 **1~30개**로 상향하였습니다.
- 테이블 초기 생성 및 세팅 데이터 마이그레이션 중 `DB_POOL_SIZE`의 기본값을 기존 5에서 **10**으로 수정하였습니다.

### 2. UI 및 환경설정 반영 (`library_settings.html`, `general.js`)
- 환경설정 화면 내 라이브러리 DB 커넥션 입력 필드의 `max` 속성을 20에서 **30**으로 변경하고 기본값을 10으로 안내하도록 레이블을 갱신하였습니다.
- 브라우저 클라이언트 JS의 초기 바인딩 로직에서 DB_POOL_SIZE의 fallback 기본값을 `'5'`에서 `'10'`으로 변경하였습니다.

### 3. 작업 이력 및 버그 문서 수집
- `./docs/bug/20260629_bugfix_db_pool_exhausted.md`를 생성하여 장애 상세 내역과 조치 내용을 영구 기록하였습니다.
- `workflow.md` 마스터 작업 이력 파일에 본 작업 내용을 수록하였습니다.
- `collect_docs.py` 스크립트를 성공적으로 작동시켜 세션 데이터를 아카이브 완료하였습니다.
