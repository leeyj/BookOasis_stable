---
title: Walkthrough - hybrid_redis_cache
project: BookOasis
category: history
date: 2026-07-19
type: walkthrough
---
# 하이브리드 Redis 캐시 레이어 도입 결과 (Walkthrough)

SQLite DB 손상 방지를 위해 Redis를 완충 캐시로 도입하되, 네이티브 및 로컬 개발 환경에서의 설치 부담을 없애기 위해 하이브리드(Fallback) 모드로 작동하도록 구현하였습니다.

## 변경 사항 (Changes Made)

### [Dependencies & Configurations]
- [requirements.txt](file:///c:/project/media_server/requirements.txt): `redis==5.0.1` 패키지 의존성 추가.
- [.env](file:///c:/project/media_server/.env): `REDIS_URL` 환경 변수 템플릿 추가 (기본 주석 해제하여 타겟 DB 인덱스 지정 가능).
- [docker-compose.yml](file:///c:/project/media_server/docker-compose.yml) & [docker-compose.ghcr.yml](file:///c:/project/media_server/docker-compose.ghcr.yml) & [docker-compose.override.example.yml](file:///c:/project/media_server/docker-compose.override.example.yml):
  - `redis:7-alpine` 공식 컨테이너 서비스를 추가 연동.
  - 컨테이너 종료 유예시간 `stop_grace_period`을 `1m`으로 상향 설정하여 프로세스가 안전하게 캐시를 비우고 퇴출될 시간을 보장.

### [Cache & Services]
- [utils/redis_helper.py](file:///c:/project/media_server/utils/redis_helper.py):
  - Redis 클라이언트 관리 및 Fallback 모드 가드 구현.
  - 모든 Redis Key 앞에 `bookoasis:` 접두사를 강제하여 타 시스템과의 키 충돌을 원천 격리 방지.
- [services/reading_progress_service.py](file:///c:/project/media_server/services/reading_progress_service.py):
  - `record_progress()`: 레디스 가동 시 메모리 해시 및 펜딩 큐에 우선 저장하고 SQLite 디스크 쓰기를 전면 스킵.
  - `get_progress_state()`: 조회 요청 시 레디스 캐시 메모리의 최신 상태를 머지(Override)하여 데이터 일치성 보장.
  - `flush_progress_cache()`: 레디스 캐시를 SQLite DB에 벌크 upsert하고 정리하는 비동기 동기화 모듈 신설.
- [services/scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py):
  - 스케줄러 기동 시 `flush_progress_cache`를 1분 주기로 기동하는 백그라운드 interval 스케줄 자동 등록.
- [core.py](file:///c:/project/media_server/core.py):
  - `_graceful_shutdown()` 종료 핸들러 내에 `flush_progress_cache()` 실행 구문을 추가하여, 프로세스 다운 시점의 미동기화 캐시를 안전하게 SQLite에 강제 병합 후 안전 종료되도록 정비.

---

## 검증 결과 (Verification Results)

### IDE 린트 경고 대응
- 로컬 `utils/redis_helper.py` 파일의 `Cannot find module 'redis'` 경고는 가상환경 내 `redis` 라이브러리가 미설치되어 발생한 린트 오류입니다. 사용자가 직접 로컬 터미널에서 아래 패키지 설치 명령을 수행하면 즉시 해소됩니다:
  `pip install redis` (또는 `.venv/Scripts/python -m pip install redis`)
