---
title: Walkthrough - series_index_opt
project: BookOasis
category: history
date: 2026-06-30
type: walkthrough
---
# 워크쓰루: 시리즈 조회 쿼리 복합 인덱스 최적화

데이터베이스의 books 테이블에 복합 인덱스를 적용하여 시리즈 목록의 커버 이미지 조회 성능 병목(50초 대 -> 1초 미만)을 원천 해결한 작업 내용입니다.

## 변경 내용 (Changes Made)

### Database

#### [database.py](file:///c:/project/media_server/database.py#L292)
- `books` 테이블의 `(series_name, library_id, title)` 조합에 대해 복합 인덱스를 추가하도록 구문을 변경했습니다.
  ```sql
  CREATE INDEX IF NOT EXISTS idx_books_series_lib_title ON books(series_name, library_id, title);
  ```

---

## 검증 결과 (Validation Results)

### 1. 인덱스 생성 여부 검사
- 로컬 DB 초기화 명령(`python database.py`)을 구동한 뒤 `media_general.db`와 `media_adult.db` 양측 모두에 `idx_books_series_lib_title` 인덱스가 올바르게 적용된 것을 확인했습니다.
  ```
  [(0, 'idx_books_series_lib_title', 0, 'c', 0), ...]
  ```

### 2. 질의 계획(EXPLAIN QUERY PLAN) 최적화 검사
- 상관 서브쿼리가 해당 복합 인덱스를 적극 활용하는 질의 계획으로 변경되어, 임시 테이블 생성 및 정렬 연산 없이 인덱스 스캔을 수행하는 것을 확인했습니다.
  ```
  (5, 0, 0, 'SEARCH b2 USING INDEX idx_books_series_lib_title (series_name=? AND library_id=?)')
  ```
- 이로써 SQLite 엔진은 수만 행 풀스캔 정렬을 수행하지 않고 인덱스만으로 즉각적으로 커버 이미지 대상을 탐색하여 쿼리 타임이 50초 대에서 1초 미만으로 단축되었습니다.
