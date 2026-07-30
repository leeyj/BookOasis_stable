---
title: "스트리밍 API 내 예외 발생 시 DB 커넥션 누수 버그 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, database, connection-leak, stream]
---

# 🧠 [Bugfix] 스트리밍 API 내 예외 발생 시 DB 커넥션 누수 오류 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 스캔 중 혹은 다량의 이미지 로드가 병행되는 만화책 열람(연속 스크롤 뷰어 기동 등) 상황
- **장애 현상**: DB 풀 설정을 10개 이상으로 증설했음에도 불구하고 `Database connection pool exhausted` 오류가 빈발하며 특정 시점 이후 사이트 전체가 마비되는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 만화책 연속 스크롤 모드는 순간적으로 수십 장의 이미지 리소스를 병행 로딩합니다.
- 이 과정에서 SQLite 락(Lock) 경합으로 인해 오프셋 쿼리 중 1~2개라도 예외를 유발하면, 누적된 커넥션 누수로 인해 단 몇 분 만에 서비스 이용이 불가능해집니다.

---

## 3. 원인 파악 (Root Cause)
- [stream_service.py](file:///c:/project/media_server/services/stream_service.py)의 `get_file_path` 및 `extract_page` 메소드 내에서 `conn = database.get_connection()` 호출 후 단순 로직 하단에서 `conn.close()`를 수행하도록 설계되어 있었습니다.
- 쿼리 실행 도중 예외가 발생할 경우, 호출 실행 흐름이 `except` 블록으로 즉시 분기되면서 그 뒤에 정의된 `conn.close()` 문이 스킵되어 커넥션이 반환되지 않고 묶여버리는 **Connection Leak**이 주원인이었습니다.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [stream_service.py](file:///c:/project/media_server/services/stream_service.py#L43-L95,L177-L188)
- `get_file_path` 와 `extract_page` 내부의 데이터베이스 커넥션 획득 및 쿼리 구문에 `try-finally` 구문을 강제하였습니다.
- 쿼리 결과 성공 여부나 예외(SQLite OperationalError 등) 발생 여부와 상관없이, 실행 후에는 무조건 `finally` 블록의 `conn.close()`가 확실히 실행되도록 수정해 완벽한 누수 방지를 확보하였습니다.

---

## 5. 최종 검증 (Verification)
- 스캔 구동 도중 다중 이미지 요청이 지속 인입되는 만화책 뷰어를 연속 스크롤로 고속 넘기며 부하를 인가하였을 때, 더 이상 콘솔 및 네트워크 탭에 `connection pool exhausted` 관련 API 실패가 유발되지 않고 모든 페이지가 즉각 렌더링됨을 수동 확인하였습니다.
