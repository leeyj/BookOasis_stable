---
title: "MariaDB DDL 스키마 단일화(Single Source of Truth) 구조 통합 및 자동 보강 개편"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [mariadb, schema, ddl, refactoring, single_source_of_truth, db_schema_updater]
---

# 🚀 [개선] MariaDB DDL 스키마 단일화(Single Source of Truth) 구조 통합 및 자동 보강 개편

## 1. 개요
- **목적**: 기존 `tools/migrator_sqlite_to_mariadb.py`와 `tools/db_schema_updater.py` 등에 분산되어 관리되던 MariaDB 스키마 DDL 및 필수 컬럼 명세를 단일 소스(Single Source of Truth)로 일원화함.
- **효과**: 신규 기능 추가 시 스키마가 분산되어 일부 컬럼이나 테이블이 누락되던 구조적 위험을 100% 원천 제거함.

## 2. 작업 상세 내용 (수정 파일)

### 1) [`c:\project\media_server\tools\db_schema_updater.py`](file:///c:/project/media_server/tools/db_schema_updater.py) [중앙 스키마 모듈화]
- MariaDB 내 18개 전체 테이블(`libraries`, `books`, `audiobooks`, `collections`, `collection_items`, `users`, `settings` 등)의 완벽한 DDL을 `MARIADB_CENTRAL_SCHEMA` 하나의 단일 객체로 정의.
- 서버 구동 시 전체 DB/테이블/컬럼을 일괄 비교하여 누락된 테이블/컬럼 자동 생성 및 ALTER TABLE 보강 엔진 구축.

### 2) [`c:\project\media_server\tools\migrator_sqlite_to_mariadb.py`](file:///c:/project/media_server/tools/migrator_sqlite_to_mariadb.py) [하드코딩 DDL 제거]
- 중복된 하드코딩 `MARIADB_SCHEMA_DDL` 구문을 제거하고 `from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA as MARIADB_SCHEMA_DDL`로 단일 소스를 직접 공유 참조.

## 3. 결과 및 검증
- 홈 서버 배포(`python deploy.py`) 완료 (Server PID: 723321 / Worker PID: 723385).
- 서버 구동 시 스키마 자동 동기화 도구가 `MARIADB_CENTRAL_SCHEMA` 기준 100% 무결하게 마이그레이션 및 동기화됨을 확인 완료.
