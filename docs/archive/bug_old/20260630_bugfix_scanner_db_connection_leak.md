---
title: "도서 스캔 과정의 DB 커넥션 누수 및 풀 크기 조정 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-30
tags: [bug, database, connection-leak, scanner]
---

# 🧠 [Bugfix] 도서 스캔 과정의 DB 커넥션 누수 및 풀 크기 조정 조치

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 대규모 도서 스캔 및 웹 서비스 병행 기동 시
- **장애 현상**: 스캔 도중 또는 스캔 후 웹 브라우저 접속 시 무한 로딩에 빠지며 `Database connection pool exhausted` 예외 발생.

---

## 2. 영향도 분석 (Impact Analysis)
- 스캔 실행 시 DB 커넥션이 누수되어 풀이 고갈되면 웹 서버(Gunicorn)가 API 요청 처리 시 DB 연결을 획득하지 못해 30초 대기 후 타임아웃 오류를 유발하고, 이로 인해 홈 화면의 도서 로딩이 차단됩니다.

---

## 3. 원인 파악 (Root Cause)
- 스캐너(`core.py`, `vfs.py`, `lazy_scanner.py`) 내에 `database.get_connection()` 호출 후 오류가 발생하거나 조건에 따른 조기 리턴 시 `conn.close()`를 보장하지 못하는 `try-finally` 누락 지점들이 존재하여 커넥션 누수가 유발되었습니다.
- 또한 동시 다발적인 웹 요청에 대응하기에 기본 DB 풀 크기인 10개가 빡빡한 원인도 결합되었습니다.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [database.py](file:///c:/project/media_server/database.py)
- 기본 데이터베이스 풀 크기(`DB_POOL_SIZE`)를 `10`에서 `15`로 상향하여 병렬 웹 요청에 대한 처리 여유 용량을 확보했습니다.

### [MODIFY] [core.py](file:///c:/project/media_server/tools/scanner/core.py)
- `scanner_print_control` 및 주요 스캔 로직을 래핑하고, `try-finally` 문을 사용하여 작업 완료 혹은 오류 시점에 `conn.close()`가 반드시 실행되도록 수정했습니다.

### [MODIFY] [vfs.py](file:///c:/project/media_server/tools/scanner/vfs.py)
- `trigger_vfs_refresh` 내 DB 조회 구간 전체에 `try-finally` 예외 차단벽을 적용하여 비정상 종료 시에도 커넥션을 해제하도록 보장했습니다.

### [MODIFY] [lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py)
- 매 루프 회차에서 커넥션을 획득한 후 처리하는 로직을 감시하고, 상위 `finally` 블록에서 잔존 커넥션을 확실히 회수하도록 수정했습니다.

---

## 5. 최종 검증 (Verification)
- 모든 수정 대상 파일에 대해 `python -m py_compile` 컴파일 정상 통과를 완료했습니다.
