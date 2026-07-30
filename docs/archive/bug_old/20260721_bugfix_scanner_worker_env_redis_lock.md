---
title: "스캐너 워커 환경 변수 로드 누락 및 Redis 폴백 오작동 버그 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-21
tags: [bugfix, env, redis, lock, sqlite, fallback]
---

# 🐛 스캐너 워커 환경 변수 로드 누락 및 Redis 폴백 오작동 버그 수정

## 1. 버그 및 성능 이슈 내역
- **현상:** 홈 서버 환경에서 소스 코드를 배포하여 가동했음에도 불구하고, 스캔 시 여전히 `Scanner flush failed due to persistent DB contention.` 에러와 함께 전체 스캔이 무한 루프처럼 다시 처음부터 실행(재시도)되는 문제가 발생함.
- **원인:**
  1. **환경 변수 로드 누락**: `manage.sh`를 통해 독립 백그라운드로 실행되는 `tools/scanner_worker.py` 내부에서 `.env` 환경 변수 파일을 로드하지 않아 `REDIS_URL` 환경 변수를 읽지 못하는(`None`) 현상이 발생함.
  2. **Redis 비활성화(폴백) 시 락 획득 오작동**: `REDIS_URL`이 없거나 Redis 서버 연결이 불가능할 때 `utils/redis_helper.py` 내의 `redis_acquire_lock` 함수가 단순히 `None`을 반환함. 이로 인해 호출부(`engine.py` 등)는 이를 "실제 다른 작업에 의해 분산 락이 선점되어 바쁜 상태(Busy)"로 오인하여 6회 지연 대기 후 최종적으로 `DB contention` 예외를 발생시키며 중단 및 재시도를 유발함. 즉, Redis가 없을 때 작동해야 할 SQLite 직접 쓰기(폴백)가 작동하지 못함.

## 2. 영향도
- **시스템 안정성:** 독립 스캐너 워커 구동 시 Redis 분산 락 관련 환경변수 누락으로 스캔 작업이 항상 실패하며, 실패 시 스케줄러 재시도 정책에 의해 스캔이 계속 처음부터 다시 실행(가~하 자음 순회 무한 반복)됨.

## 3. 수정 사항
1. **[tools/scanner_worker.py](file:///c:/project/media_server/tools/scanner_worker.py)**
   - 스크립트 실행부 진입점에 `dotenv.load_dotenv()`를 호출하여 프로젝트 루트의 `.env` 파일에 기록된 환경 변수(예: `REDIS_URL`)를 강제로 로드하도록 보완.
2. **[utils/redis_helper.py](file:///c:/project/media_server/utils/redis_helper.py)**
   - `redis_acquire_lock()`에서 Redis 클라이언트가 활성화되지 않았을 경우(`None`), `None` 대신 가상의 더미 토큰(`"mock_sqlite_direct_token"`)을 반환하도록 수정하여 SQLite 직접 쓰기 폴백 모드를 안전하게 활성화함.

## 4. 해결 사항 및 E2E 검증 결과
- **Redis 연동 정상화:** 스캐너 워커 프로세스에서 `.env` 환경 변수를 정상적으로 불러옴에 따라 로컬 Redis 서버(`redis://127.0.0.1:6379/9`)와의 분산 락 연동이 정상 작동함.
- **폴백 메커니즘 복구:** Redis가 사용 불가능한 상태여도 예외적으로 가상 토큰을 리턴하게 됨으로써, 경합 실패로 인지되지 않고 SQLite 직접 쓰기 트랜잭션이 중단 없이 수행됨.
