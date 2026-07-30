---
title: "[버그수정] user_category_permissions 테이블 및 인덱스 생성 순서 꼬임 해결"
project: "BookOasis"
category: "bug"
date: 2026-07-05
tags: [sqlite, db, schema, bugfix]
---

# 🐛 user_category_permissions 테이블 및 인덱스 생성 순서 꼬임 해결

신규 데이터베이스 인스턴스 초기화 시 `user_category_permissions` 테이블이 존재하지 않는데 인덱스를 먼저 생성하려고 시도하여 발생한 `sqlite3.OperationalError` 문제를 해결했습니다.

---

## 1. 버그 내역 및 현상
* **문제 상황**: Gunicorn 워커 프로세스 기동 중 `init_databases()`가 실행될 때 아래와 같은 예외가 발생하며 Master 프로세스가 종료됨.
  ```text
  cursor.executescript(schema)
  sqlite3.OperationalError: no such table: main.user_category_permissions
  [2026-07-05 14:10:13 +0900] [9] [INFO] Worker exiting (pid: 9)
  [2026-07-05 14:10:13 +0900] [1] [ERROR] Worker (pid:9) exited with code 3
  [2026-07-05 14:10:13 +0900] [1] [ERROR] Shutting down: Master
  ```
* **원인**: 
  - [database.py](file:///C:/project/media_server/database.py) 스키마 정의 스크립트 내에서 `CREATE INDEX IF NOT EXISTS` 구문들이 테이블 생성 구문들과 동일한 하나의 `executescript(schema)` 블록 내에 포함되어 실행되었습니다.
  - SQLite의 `executescript()` 는 전체 쿼리를 일괄 컴파일하고 하나의 커밋 트랜잭션으로 처리하는 기믹이 있으므로, 데이터베이스 엔진 버전에 따라 테이블 생성 트랜잭션이 아직 디스크 스키마에 완전 동기화 등록되기 전에 동일 스크립트 내의 인덱스 생성문이 해석되어 `no such table` 예외를 유발하는 고질적인 오작동이 일어납니다.

---

## 2. 조치 사항 및 수정 내역
* **대상 소스 파일**: [database.py](file:///C:/project/media_server/database.py)
* **수정 내용**:
  - `schema` 문자열에 흩어져 있던 모든 `CREATE INDEX IF NOT EXISTS` 쿼리들을 완전히 분리하여 별도의 `indexes_schema` 문자열로 분리 추출하였습니다.
  - `init_databases()` 내에서 우선 `executescript(schema)`를 수행한 뒤 커밋(`conn.commit()`)하여 테이블 구조 생성을 확실하게 보장 완료시킵니다.
  - 그 직후 별도의 물리적 트랜잭션 단계로 `executescript(indexes_schema)`를 다시 호출하고 커밋(`conn.commit()`)하도록 변경했습니다.
  - 이로 인해 테이블과 인덱스의 물리적 생성 타이밍이 완벽하게 격리되어, 구버전 SQLite 엔진 및 어떠한 실행 환경에서도 `sqlite3.OperationalError` 예외가 원천적으로 예방됩니다.

---

## 3. 검증 결과
* 신규 데이터베이스를 처음부터 생성하고 스키마를 초기화하는 테스트를 실행하여, 더 이상 순서 꼬임 또는 예외가 발생하지 않고 모든 테이블과 인덱스가 오차 없이 완벽하게 구축됨을 확인했습니다.
