---
title: "database.py 런타임 SQL 자동 변환 래퍼(_convert_sql) 완전 제거 및 경량화"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [database, mariadb, wrapper, performance, native_sql, improvement]
---

# 🚀 [개선] database.py 런타임 SQL 자동 변환 래퍼(_convert_sql) 완전 제거 및 경량화

## 1. 개요 및 배경
- **배경**: `repositories/mariadb/` 전용 Native SQL 레이어가 성공적으로 구축됨에 따라, PyMySQL 커서 단에서 실행되던 런타임 정규식 SQL 방언 변환기(`_convert_sql`)가 무용지물이 됨.
- **목적**: 런타임 정규식 치환 오버헤드를 완전 삭제하여 DB 처리 속도를 향상시키고 쿼리가 100% 원형(Native SQL) 그대로 MariaDB 드라이버에 전달되도록 경량화.

## 2. 주요 개선 사항 (수정 소스 파일)

### 1) [`c:\project\media_server\database.py`](file:///c:/project/media_server/database.py)
- `MariadbCursorWrapper._convert_sql` 내 모든 정규식 치환 연산자(?, AUTOINCREMENT, strftime, RESERVED KEYWORDS 백틱 치환 등) 전면 제거.
- SQLite 전용 `PRAGMA` 및 `BEGIN` 제어 명령에 대한 얇은 안전 우회(`SELECT 1`)만 남기고, 모든 쿼리를 무변형 패스스루(Passthrough) 처리.

## 3. 기대 효과
- **CPU 및 메모리 오버헤드 0화**: 매 쿼리마다 실행되던 10여 가지 정규식 검사 및 치환 과정 제거로 대용량 트랜잭션 수용 능력 향상.
- **예측 가능성 향상**: 개발자가 작성한 Native SQL이 100% 동일하게 MariaDB 서버로 전달되어 디버깅 및 프로파일링 용이.
