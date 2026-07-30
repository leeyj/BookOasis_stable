---
title: "스캔 중 메모리 임계값 DB 조회 락 경합으로 인한 disk I/O error 로그 제거"
category: "bugfix"
date: 2026-07-22
severity: "low"
affected_files:
  - "tools/scanner/memory_helper.py"
tags: [memory_helper, sqlite, lock_contention, cache_ttl]
---

# 스캔 중 메모리 임계값 DB 조회 락 경합으로 인한 disk I/O error 로그 제거

## 1. 버그 개요
- 대량 도서 스캔 진행 시 스캐너가 DB에 쓰기(UPDATE/INSERT)를 수행하는 순간과 `memory_helper.py`에서 메모리 한도 설정(`SYSTEM_MEM_LIMIT`, `PROCESS_RSS_LIMIT`)을 읽으려는 시점이 겹치면서 간헐적으로 `disk I/O error` (또는 `database is locked`) 로그가 발생하는 현상.

## 2. 원인 분석
- `memory_helper.py`의 설정 캐시 유효기간(TTL)이 30초로 다소 짧아 대량 스캔 중 반복적인 DB 조회가 일어남.
- DB 락 경합 예외 발생 시 에러 메시지를 콘솔에 출력하도록 되어있어 노이즈 로그가 유발됨.

## 3. 수정 사항
- `tools/scanner/memory_helper.py`:
  - 설정 캐시 TTL을 기존 30초에서 300초(5분)로 상향 연장.
  - DB 락 경합 시 기존 메모리에 든 캐시값을 자동 연장 활용하도록 개선하여 디스크 I/O 조회를 최소화하고 노이즈 로그를 완전 제거.

## 4. 검증 결과
- 스캔 도중 DB 쓰기 작업이 몰려도 `disk I/O error` 로그 없이 300초 캐시를 이용하여 안정적이고 조용하게 메모리 한도 체크가 작동함을 확인함.
