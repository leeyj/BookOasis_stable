---
title: "파싱 연산 지연 시 DB Lock 장기 점유 및 WAL 저널 손상(Malformed DB) 방지"
category: "bugfix"
date: 2026-07-22
severity: "high"
affected_files:
  - "tools/lazy_scanner.py"
tags: [lazy_scanner, malformed_db, sqlite, wal_checkpoint, lock_contention]
---

# 파싱 연산 지연 시 DB Lock 장기 점유 및 WAL 저널 손상(Malformed DB) 방지

## 1. 버그 개요
- 깨진 메타데이터 문서를 파싱하거나 Regex Fallback 연산을 수행할 때 수초 간 파일 I/O 및 정규식 연산 지연이 발생함.
- 기존에는 이 연산 지연 동안 DB 커넥션 및 WAL 저널 트랜잭션이 지속적으로 열려 있어, 대기 중 프로세스 강제 중단(SIGTERM/배포) 발생 시 WAL 저널 파일이 손상(`database disk image is malformed`)되는 버그 발생.

## 2. 수정 사항
- `tools/lazy_scanner.py`:
  - `conn.close()` 및 `finally` 마감 블록 시점에 `PRAGMA wal_checkpoint(TRUNCATE);` 구문을 자동 실행하도록 보완.
  - 프로세스가 자진 종료되거나 외부 시그널(SIGTERM)로 마감될 때 WAL 임시 저널 파일(`media_general.db-wal`)의 변경 사항을 즉시 메인 DB 파일에 동기화하고 깨끗이 비워 DB 파일 물리 손상을 원천 방지함.

## 3. 검증 결과
- 스캔 도중 비상 중단 및 재기동이 발생해도 SQLite WAL 저널 파일이 완전하게 체크포인트되어 `PRAGMA integrity_check` 결과 ok를 100% 유지함을 확인.
