---
title: "시리즈 목록 커버 이미지 서브쿼리 성능 저하 조치 (복합 인덱스 적용)"
project: "BookOasis"
category: "bugfix"
date: 2026-06-30
tags: [bug, database, sqlite, index, performance]
---

# 🧠 [Bugfix] 시리즈 목록 커버 이미지 서브쿼리 성능 저하 조치 (복합 인덱스 적용)

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 대규모 만화책(수만 권 이상)이 등록된 상태에서 도서 라이브러리 목록 진입 및 시리즈 탭 로딩 시
- **장애 현상**: 웹 페이지 로딩 시간이 50초 이상 소요되어 페이지 응답이 극도로 느려지는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 사용자가 라이브러리의 시리즈 목록을 조회하려 할 때 50초 이상의 대기 시간이 발생하여 서비스가 사실상 정지된 것과 같은 심각한 사용자 경험 저하를 야범함.

---

## 3. 원인 파악 (Root Cause)
- 시리즈 목록을 조회하는 메인 쿼리에서 그룹마다 `cover_image`와 `cover_updated_at`을 구하기 위해 상관 서브쿼리(Correlated Subquery) 2개를 실행함:
  ```sql
  (SELECT b2.cover_image FROM books b2 
   WHERE b2.series_name = b.series_name AND b2.library_id = b.library_id 
     AND b2.cover_image IS NOT NULL AND b2.cover_image != '' 
   ORDER BY b2.title ASC LIMIT 1)
  ```
- 기존에는 `books` 테이블에 `idx_books_series_name` (단일 컬럼) 인덱스만 존재하여 `(series_name, library_id)` 조건에 대해 정밀 탐색이 불가능했으며, `ORDER BY title` 정렬을 지원할 인덱스도 없었음.
- 이로 인해 SQLite 엔진이 서브쿼리마다 테이블을 거의 풀스캔 및 정렬하게 되어, 968개 그룹 기준 수천만 번 이상의 행을 스캔하게 됨으로써 병목(50초 대 소요)이 발생함.

---

## 4. 조치 사항 (Remediation Actions)
- `database.py`의 `init_databases` 스키마 초기화 부분에 `(series_name, library_id, title)` 복합 인덱스 `idx_books_series_lib_title`를 생성하도록 쿼리 추가:
  - 파일: [database.py](file:///c:/project/media_server/database.py#L292)
  - 내용: `CREATE INDEX IF NOT EXISTS idx_books_series_lib_title ON books(series_name, library_id, title);`
- 복합 인덱스 적용 결과, `EXPLAIN QUERY PLAN` 상에서 상관 서브쿼리가 인덱스를 활용한 빠른 정밀 탐색(`SEARCH b2 USING INDEX idx_books_series_lib_title (series_name=? AND library_id=?)`)으로 동작하도록 최적화되어 50초대의 지연 시간을 1초 미만으로 단축시킴.

---

## 5. 최종 검증 (Verification Results)
- 로컬 개발 환경에서 데이터베이스 스키마 마이그레이션 (`python database.py`) 수행 후 인덱스가 양측 DB(`media_general.db`, `media_adult.db`)에 정상 생성되었음을 확인 완료.
- `EXPLAIN QUERY PLAN` 분석을 통해 서브쿼리가 신규 복합 인덱스를 올바르게 타서 질의 계획이 최적화됨을 검증함.
