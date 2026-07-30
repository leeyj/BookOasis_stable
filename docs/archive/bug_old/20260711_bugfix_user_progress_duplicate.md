---
title: "최근 읽은 도서 진척도 중복 노출 결함 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-11
tags: [bugfix, database, user_progress, concurrency]
---

# 최근 읽은 도서 진척도 중복 노출 결함 조치

## 1. 버그 내역 및 증상
- 사용자가 최근 읽은 도서 목록(대시보드)을 조회할 때, 동일한 도서의 카드(표지, 읽은 페이지 수, 진행률 등 완전히 동일한 내역)가 2개 이상 중복되어 가로 배열로 노출되는 현상 발생.
- 웹 브라우저 새로고침이나 일시적인 네트워크 지연 시에 진척도 저장 API 요청이 동시에 전송되면 현상이 더 잦아짐.

## 2. 원인 분석
- **경쟁 상태 (Race Condition)**: `services/stream_service.py`의 `save_progress` 로직이 `SELECT` 검사 후 `INSERT` 하는 패턴으로 작성되어 있어, 동시에 들어온 중복 요청이 `SELECT` 검사를 모두 통과한 뒤 `INSERT`를 순차 실행하여 2개 이상의 동일 `(user_id, book_id)` 로우가 삽입됨.
- **UNIQUE 제약조건 부재**: SQLite 데이터베이스 `user_progress` 테이블의 `(book_id, user_id)` 조합에 고유 제약조건이나 유니크 인덱스가 부재하여 DB 수준에서 중복 유입을 제어하지 못함.

## 3. 조치 사항
1. **데이터베이스 마이그레이션 (`database.py`)**:
   - `init_databases()` 초기 구동 시 `user_progress` 내의 중복 로우들을 감지하여 가장 최신 1개만 남기고 안전하게 삭제하는 쿼리 적용.
   - 기존의 비-고유(Non-unique) 인덱스 `idx_user_progress_book_user`를 완전히 `DROP`하고, `(book_id, user_id)`에 대한 `CREATE UNIQUE INDEX`를 인덱스 정의에 새롭게 반영하여 데이터베이스 무결성 사수를 확정함.
2. **저장 API 멱등성 보장 (`services/stream_service.py`)**:
   - `SELECT` 결과 유무에 따른 `INSERT`/`UPDATE` 분기 처리를 개선하여, 우선 `INSERT OR IGNORE`로 더미 레코드를 확보한 뒤 무조건 `UPDATE`를 쳐서 동일 데이터 갱신 시에도 경쟁 상태로 인한 중복 로우가 발생하지 않도록 멱등적인 2단계 로직으로 전면 리팩토링함.

## 4. 해결 확인 및 영향도
- 로컬 데이터베이스(`media_general.db`, `media_adult.db`)의 기존 적체되어 있던 총 464개의 중복 로우가 안전하게 제거되었으며, 중복 테스트 수행 시 고유 제약 조건 에러가 정상 작동함을 확인.
- 프론트엔드 대시보드 화면에 더 이상 중복 카드가 노출되지 않고 한 건으로 완벽히 통합 렌더링됨.
