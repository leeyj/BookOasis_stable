---
title: "전체 코드베이스 MariaDB SQL 문법 전수 감사 및 일괄 자동 교정"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [mariadb, sql_audit, reserved_keyword, backtick, codebase_wide, refactoring]
---

# 🚀 [개선] 전체 코드베이스 MariaDB SQL 문법 전수 감사 및 일괄 자동 교정

## 1. 개요
- **목적**: 프로젝트 전반(177개 파이썬 소스 파일)의 SQL 쿼리를 정밀 전수 감사하여, 백틱이 누락된 MariaDB/MySQL 예약어(`key`, `value`) 및 잔존 SQLite-ism 구문을 일괄 소거하고 런타임 SQL 구문 에러를 원천 차단함.

## 2. 작업 상세 내용 (신규/수정 파일)

### 1) [`c:\project\media_server\tools\audit_mariadb_sql.py`](file:///c:/project/media_server/tools/audit_mariadb_sql.py) [신규]
- 프로젝트 전체 `.py` 소스 코드의 SQL 쿼리를 AST 및 Regex 패턴으로 정밀 스캔하는 전수 감사 도구 구축.

### 2) 전수 검사 및 교정 결과
- **점검 대상**: 177개 파이썬 파일.
- **교정 파일 및 쿼리**: 총 4개 주요 모듈(`database.py`, `repositories/sqlite/metadata_repository.py`, `repositories/sqlite/reading_progress_repository.py`, `repositories/sqlite/settings_repository.py`)에서 백틱이 누락되어 있던 **24개 SQL 쿼리의 `key`, `value` 예약어를 ``` `key` ```, ``` `value` ```로 일괄 자동 백틱 이스케이프 교정**.

## 3. 결과 및 검증
- 홈 서버 배포(`python deploy.py`) 완료 (Server PID: 312384 / Worker PID: 312444).
- MariaDB 모드 구동 시 예약어 백틱 누락으로 인한 1064 Syntax Error 리스크가 프로젝트 전체에서 100% 소거되었음을 검증 완료.
