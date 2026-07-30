---
title: Task - scanner_db_lock_concurrency_fix
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 스캐너 DB 락 및 동시성 병목 수정 작업 목록

- [x] `tools/scanner.py` 코드 수정
  - [x] 자체 DB 커넥터 `get_db_connection`을 제거하고 `database.get_connection` 사용하도록 변경
  - [x] 벌크 커밋 방식(50권 단위)을 매 권(Book) 작업 성공 시 즉시 커밋하는 방식으로 세분화
- [x] 로컬 구문 컴파일 및 정밀 검증
  - [x] `python deploy.py`를 통한 홈 서버 원격지 배포 및 데몬 재구동
- [x] 버그 수정 이력 문서화 및 전역 동기화
  - [x] `docs/bug/20260620_bugfix_scanner_db_lock_concurrency.md` 신설
  - [x] `docs/workflow.md` 이력 업데이트
  - [x] `walkthrough.md` 결과 문서 작성
  - [x] `tools/collect_docs.py` 실행
