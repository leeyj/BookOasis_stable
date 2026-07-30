---
title: "스캐너 가동 중 데이터베이스 락(Lock) 점유 및 읽기 지연 버그 수정"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [database-lock, sqlite, scanner, concurrency]
---

# 🧠 스캐너 가동 중 데이터베이스 락(Lock) 점유 및 읽기 지연 버그 수정

## 1. 개요 및 버그 내용
- **현상**: 백그라운드 라이브러리 스캐너가 대규모 작품 스캔을 수행 중일 때, 만화책 뷰어에서 다음 페이지 로딩이나 작품 조회가 불가능하거나 극도로 지연되는 현상 발생.
- **원인**: SQLite 쓰기 트랜잭션이 한꺼번에 락을 과다 점유하여 동시 읽기가 불완전해진 동시성 문제.

## 2. 원인 분석
1. **커넥션 통일성 부재**: 스캐너([`tools/scanner.py`](file:///c:/project/media_server/tools/scanner.py))가 공용 커넥션 헬퍼([`database.py`](file:///c:/project/media_server/database.py))를 사용하지 않고 개별 `sqlite3.connect`를 가동함. 이로 인해 `timeout=30.0` 설정 및 `PRAGMA journal_mode=WAL;` 등 동시성 제어 프래그마가 스캐너 측에서 적용되지 않음.
2. **비대한 트랜잭션 단위**: 50권 단위로만 커밋을 실행함으로써, 수만 페이지의 이미지 오프셋(Insert) 데이터가 하나의 쓰기 트랜잭션에 묶여 독점 락(Exclusive Lock) 점유가 장시간 유지되어 읽기 세션을 고사시킴.

## 3. 조치 내용
1. **스캐너 데이터베이스 커넥션 통일**:
   - `tools/scanner.py`의 `get_db_connection`을 제거하고, 공용 라이브러리 `import database` 구문을 활용해 `database.get_connection(db_type)`을 호출하도록 단일화. 타임아웃 30초 및 WAL 강제 모드를 스캐너 세션에서도 일관되게 공유.
   - `services/book_scan_service.py`에서도 자체 정의 함수 대신 `database.get_connection(db_type)`을 사용하게끔 변경하여 모듈 의존성 정리.
2. **트랜잭션 커밋 주기 축소 (매 권 단위)**:
   - `tools/scanner.py` 내의 `scan_library` 데이터 쓰기 루프에서 도서 갱신 혹은 등록(`db_action_taken = True`)이 1건 일어날 때마다 즉시 `conn.commit()`을 수행하도록 수정.
   - 쓰기 트랜잭션 점유를 ms 단위로 낮춰 스캐너가 구동 중인 상태에서도 동시 읽기(WAL)가 완벽히 매끄럽게 통하도록 보장.

## 4. 결과 및 검증
- 수정 적용 후 원격 홈 서버 배포 및 Gunicorn 데몬 정상 기동 확인.
- 백그라운드 스캔이 돌아가며 수천 개 파일 오프셋을 등록하고 있을 때에도, 뷰어에 진입하여 끊김이나 지연(Database is locked) 없이 실시간 페이지 로드가 잘 동작하는 것을 수동 검증 완료.
