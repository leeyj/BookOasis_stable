---
title: "SQLite 비상수 기본값 마이그레이션 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, database, migration, sqlite]
---

# 🐛 SQLite 비상수 기본값 마이그레이션 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 라이브러리 목록 진입 또는 신규 도서 추가 시 `no such column: cover_updated_at` 오류가 발생하여 서비스 조회가 중단되는 현상 발생.

## 2. 원인 분석 (Root Cause Analysis)
- `database.py`의 `init_databases` 호출 시 기존 하위 호환을 보장하기 위해 `ALTER TABLE books ADD COLUMN cover_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP` 명령이 실행됨.
- 그러나 SQLite 엔진에서는 `ALTER TABLE ADD COLUMN` 쿼리 수행 시 `CURRENT_TIMESTAMP`와 같은 동적인 비상수(non-constant) 함수를 `DEFAULT` 값으로 지정하여 컬럼을 추가할 수 없는 규격 상 제약이 존재함.
- 이 제약 조건으로 인해 `sqlite3.OperationalError: Cannot add a column with non-constant default` 예외가 발생했으나, 마이그레이션 코드가 이 오류를 단순 `pass` 처리하도록 예외 처리가 되어 있어 오류 메시지 없이 컬럼 생성이 무시되었음.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [database.py](file:///c:/project/media_server/database.py)
  - `ALTER TABLE books ADD COLUMN cover_updated_at DATETIME` 명령을 통해 상수/기본값 지정 없이 컬럼만 선축출하도록 수정함.
  - 이어서 `UPDATE books SET cover_updated_at = CURRENT_TIMESTAMP WHERE cover_updated_at IS NULL` 문을 실행해 기존 데이터 및 기본값을 개별 처리하도록 변경함.

## 4. 결과 검증 (Verification Results)
- 코드를 원격 홈 서버에 배포한 후 서비스를 재기동함.
- 서버 측 SQLite DB 조회(`PRAGMA table_info(books)`) 결과, `media_general.db` 및 `media_adult.db` 양측 모두에 `cover_updated_at` 컬럼이 누락 없이 정상적으로 생성되었음을 최종 검증 완료함.
