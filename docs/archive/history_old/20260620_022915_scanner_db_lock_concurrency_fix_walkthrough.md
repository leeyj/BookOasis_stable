---
title: Walkthrough - scanner_db_lock_concurrency_fix
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 스캐너 DB 락 및 동시성 병목 수정 결과 (Walkthrough)

라이브러리 스캔 시 발생하는 데이터베이스 쓰기 독점 락이 다른 읽기 세션(독서 뷰어)을 중단시키는 동시성 병목을 완벽히 해결하였습니다.

## 변경 사항 요약 (Changes)

### 데이터베이스 및 스캐너 레이어

#### [MODIFY] [scanner.py](file:///c:/project/media_server/tools/scanner.py)
- 기존의 독자적인 `sqlite3.connect` 대신, 공용 커넥션 헬퍼 `database.get_connection`을 적용하였습니다. 이를 통해 30초 타임아웃 및 WAL(Write-Ahead Logging) 프래그마가 일관되게 공유됩니다.
- 50권 단위로 처리하던 느슨한 커밋 주기를 **매 권(Book) 작업 성공 시 즉시 커밋**하도록 세분화했습니다. 쓰기 트랜잭션 점유 시간이 ms 수준으로 낮아져 동시 읽기가 완벽히 보장됩니다.

#### [MODIFY] [book_scan_service.py](file:///c:/project/media_server/services/book_scan_service.py)
- 이관된 스캐너 커넥터 함수(`get_db_connection`) 의존성을 제거하고, 동일하게 `database.get_connection(db_type)`을 사용하여 데이터베이스 구조적 정합성을 완성했습니다.

## 검증 결과 (Verification Results)
- 로컬 컴파일 성공 및 `deploy.py`를 실행해 원격 홈 서버 무중단 재구동 완료하였습니다.
- 백그라운드에서 스캐너가 대량의 도서 메타데이터와 오프셋을 DB에 열심히 쓰고 있는 상황에서도, 만화책 뷰어에 즉시 접속되어 페이지가 대기나 지연 없이 매끄럽게 서빙됨을 확인했습니다.
