---
title: "스캐너 실행 내 get_db_connection 참조 오류 수정"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, scanner, database, python]
---

# 🐛 스캐너 실행 내 get_db_connection 참조 오류 수정 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 파일 시스템 전체 동기화 및 라이브러리 순회 스캔 실행 시 `tools/scanner.py`의 `run_sync_scanner` 내에서 NameError 발생.
- `Could not find name 'get_db_connection'`이라는 예외가 보고되며 스캐너의 가동 루프 자체가 차단됨.

## 2. 원인 분석 (Root Cause Analysis)
- `tools/scanner.py`는 `database.py` 모듈을 `import database` 형태로 가져와 사용 중임.
- 그러나 `run_sync_scanner` 내부에서 데이터베이스 커넥션을 획득할 때 모듈 네임스페이스 없이 직접 `get_db_connection(DB_GENERAL_PATH)`를 호출함.
- 게다가 `database.py` 모듈에는 `get_db_connection`이라는 명칭 대신 커넥션 풀을 관리하는 `get_connection(db_type)` 함수가 구현되어 있으므로, 존재하지 않는 심볼을 지칭하여 NameError 오류가 유발됨.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [scanner.py](file:///c:/project/media_server/tools/scanner.py)
  - `run_sync_scanner` 함수 내부에서 일반 라이브러리 DB 접근부의 `get_db_connection(DB_GENERAL_PATH)` 호출을 `database.get_connection('general')`로 변경함.
  - 성인 라이브러리 DB 접근부의 `get_db_connection(DB_ADULT_PATH)` 호출을 `database.get_connection('adult')`로 변경하여 풀 기반의 올바른 커넥션을 호출하도록 수정함.

## 4. 결과 검증 (Verification Results)
- 수정한 뒤 파이썬 코드 컴파일 및 린트 오류가 해소되었음을 확인했으며, `run_sync_scanner` 작동 시 데이터베이스 연결이 비정상 종료 없이 매끄럽게 수립됨을 검증함.
