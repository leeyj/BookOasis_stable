---
title: "스캐너 DB 라이터(db_writer) SQLite 및 MariaDB 전용 모듈 구조적 완전 분리"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [scanner, db_writer, sqlite, mariadb, native_sql, refactoring]
---

# 🚀 [개선] 스캐너 DB 라이터(db_writer) SQLite 및 MariaDB 전용 모듈 구조적 완전 분리

## 1. 개요
- **목적**: 스캐너 엔진의 대량 펌핑 및 업서트 SQL 처리 모듈(`tools/scanner/db_writer.py`)을 SQLite와 MariaDB Native 구현체로 완벽 분리하여, SQL 변환 오버헤드를 소거하고 MariaDB 대 대량 업서트 펌핑 속도를 극대화함.

## 2. 작업 상세 내용 (신규/수정 파일)

### 1) [`c:\project\media_server\tools\scanner\db_writer_sqlite.py`](file:///c:/project/media_server/tools/scanner/db_writer_sqlite.py) [신규]
- 기존 SQLite 전용 `?` 바인딩 파라미터 및 `ON CONFLICT(file_path) DO UPDATE SET` 업서트 배치 쿼리 분리 저장.

### 2) [`c:\project\media_server\tools\scanner\db_writer_mariadb.py`](file:///c:/project/media_server/tools/scanner/db_writer_mariadb.py) [신규]
- MariaDB Native `%s` 바인딩 파라미터 및 `ON DUPLICATE KEY UPDATE` / `VALUES(col)` 고속 배치 업서트 쿼리 구축.
- Regex Transpiling 오버헤드 없이 MariaDB 엔진 전용 Native 쿼리로 실행.

### 3) [`c:\project\media_server\tools\scanner\db_writer.py`](file:///c:/project/media_server/tools/scanner/db_writer.py) [라우터 개편]
- `DB_ENGINE` 환경 변수에 따라 `db_writer_sqlite` 또는 `db_writer_mariadb` 구현체로 동적 연결 라우팅.

## 3. 결과 및 검증
- 홈 서버 배포(`python deploy.py`) 완료 (Server PID: 298451).
- MariaDB 및 SQLite 구동 환경 모두에서 라이브러리 스캔 시 쿼리 변환 오류 없이 100% Native 대량 배치 업서트 펌핑이 무결하게 수행됨을 검증 완료.
