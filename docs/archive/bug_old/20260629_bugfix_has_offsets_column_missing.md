---
title: "books 테이블 스키마 내 has_offsets 컬럼 누락으로 인한 스캔 실패 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-29
tags: [bugfix, database, scanner, schema]
---

# 🐛 books 테이블 스키마 내 has_offsets 컬럼 누락으로 인한 스캔 실패 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 일부 사용자들한테 도서 스캔 기동 시 아래와 같이 `no such column: has_offsets` 에러와 함께 스캔에 실패하는 장애가 리포트됨.
  ```text
  스캔 실패 - DB=general, LibraryID=3, 소요시간=0.07초, 에러=no such column: has_offsets
  ```

## 2. 원인 분석 (Root Cause Analysis)
- ZIP/CBZ 파일 오프셋 기능 추가 이후 `books` 테이블 스키마에 `has_offsets` 컬럼이 추가되어 관련 스캔 및 도서 정보 조회 쿼리에서 사용되고 있었음.
- 그러나 기본 스키마 초기화 코드가 정의된 `database.py`의 `CREATE TABLE IF NOT EXISTS books` 스키마 내에 `has_offsets` 컬럼 정의가 누락되어 있었음.
- 이로 인해 새로 구축되는 DB 혹은 기존 마이그레이션 적용 대상 DB에서 `has_offsets` 컬럼이 자동으로 추가되지 못하여 쿼리 실행 시 열 누락 예외가 발생함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**:
  - [database.py](file:///c:/project/media_server/database.py): `books` 테이블 스키마의 정의에 `has_offsets INTEGER DEFAULT 0` 컬럼을 명시적으로 추가했습니다.
  - 이로써 `database.init_databases()`가 호출될 때 `auto_migrate_schema` 함수가 결손된 `has_offsets` 컬럼을 런타임에 동적으로 감지하여 `ALTER TABLE books ADD COLUMN has_offsets INTEGER DEFAULT 0` 마이그레이션을 자동으로 수행하게 됩니다.

## 4. 결과 검증 (Verification Results)
- `has_offsets` 컬럼이 누락된 임시 DB 세트를 생성한 후, `database.init_databases()`를 호출하는 독립 테스트를 거쳤습니다.
- 테스트 결과 `[DB-Migration] 동적 스키마 컬럼 추가 완료: books.has_offsets (INTEGER DEFAULT 0)` 로그와 함께 DB에 자동으로 해당 컬럼이 마이그레이션되는 것을 성공적으로 검증하였습니다.
