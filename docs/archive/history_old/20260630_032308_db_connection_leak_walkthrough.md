---
title: Walkthrough - db_connection_leak
project: BookOasis
category: history
date: 2026-06-30
type: walkthrough
---
# 작업 완료 보고서 (Walkthrough)

도서 스캔 구동 시 발생하는 데이터베이스 커넥션 풀 고갈(`Database connection pool exhausted`) 버그를 수정하고, 동시 요청 처리를 개선하기 위해 DB 풀 크기 기본 설정을 최적화했습니다.

## 변경 사항

### 데이터베이스 및 스캐너 설정

#### [database.py](file:///c:/project/media_server/database.py)
- 기본 데이터베이스 풀 크기(`DB_POOL_SIZE`)를 `10`에서 `15`로 상향하여 병렬 웹 요청에 대해 넉넉한 연결 공간을 확보했습니다.

---

### 예외 발생 시 커넥션 반환 안전성 강화

#### [core.py](file:///c:/project/media_server/tools/scanner/core.py)
- `scanner_print_control` 내의 커넥션 획득부에 `try-finally`를 적용해 무조건 `close`되도록 했습니다.
- `scan_library` 및 `scan_library_covers_only` 내부 작업을 각각 래퍼 함수와 `try-finally` 블록으로 이중 감싸서, 예외가 나거나 스캔이 중단되어도 커넥션이 확실히 해제되게 보장했습니다.

#### [vfs.py](file:///c:/project/media_server/tools/scanner/vfs.py)
- `trigger_vfs_refresh` 내 DB 조회 구간 전체 및 설정 로드 구역에 `try-finally`를 보강해 누수를 차단했습니다.

#### [lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py)
- 백그라운드 락 해제 블록인 `finally` 영역 및 루프 마지막 시점에 `conn.close()`를 연동하여 안전성을 강화했습니다.

---

## 검증 결과
- 모든 대상 파이썬 파일들이 정상 컴파일(`python -m py_compile`) 통과하는지 검증을 마쳤습니다.
