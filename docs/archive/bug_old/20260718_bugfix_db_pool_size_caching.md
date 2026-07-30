---
title: "DB 커넥션 풀 크기 조회 캐싱을 통한 락 경합 및 손상 방지"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [database, cache, settings]
---

# 🧠 DB 커넥션 풀 크기 조회 캐싱을 통한 락 경합 및 손상 방지

## 1. 버그 내역
* **현상**: 스캔 도중 일반|성인 라이브러리 전환 등 DB 동시 쓰기/읽기 부하가 높은 상황에서 SQLite 데이터베이스 파일(`media_general.db`)이 깨지거나 `database disk image is malformed` 에러가 발생함.
* **원인**: `get_connection()` 호출 시 매번 `_get_pool_size_raw()`가 독자적인 물리 SQLite 연결을 열어 `settings` 테이블을 동기 조회함. 이로 인해 풀 외부의 일반 커넥션이 짧은 시간 내에 다량으로 열고 닫히며 락 경합을 유발하고 DB 파일의 구조적 손상을 일으킴.

## 2. 영향도
* **영향 범위**: 데이터베이스 연결 관리 모듈(`database.py`), 설정 정보 변경 API(`api/routes/settings_routes.py`) 및 전체적인 도서 스캔/조회 처리 안정성.

## 3. 조치 및 해결 사항
* **메모리 캐싱 도입**: `database.py` 내부에 설정값 캐시 변수(`_cached_pool_size`)와 스레드 안전성 확보를 위한 캐시 락(`_pool_size_cache_lock`)을 구현함.
* **캐시 무효화 연동**: `invalidate_pool_size_cache()` 함수를 추가하고, `settings_routes.py`에서 `DB_POOL_SIZE`가 정상 변경될 경우 캐시를 클리어하도록 수정하여 캐시가 동적으로 최신 값을 반영할 수 있도록 보장함.
* **소스 수정 내역**:
  * [database.py](file:///c:/project/media_server/database.py)
  * [settings_routes.py](file:///c:/project/media_server/api/routes/settings_routes.py)
* **검증 결과**: 수동 검증 스크립트(`scratch/test_db_cache.py`)를 통해 무효화 및 메모리 캐싱 기능이 정확하게 검증되어 정상 복구 및 경합 원인 차단을 완료함.
