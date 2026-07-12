---
title: "Phase 1 상세 설계 - 워커 역할 게이트 도입"
project: "BookOasis"
category: "roadmap"
date: 2026-07-12
tags: [roadmap, phase1, worker, scheduler, scanner, deployment]
---

# Phase 1 상세 설계 - 워커 역할 게이트 도입

## 1. 목적

Phase 1의 목적은 코드베이스를 분리하지 않고도 실행 프로세스 역할을 명확히 분리할 수 있게 만드는 것입니다.

1. web 역할: HTTP API/템플릿 렌더링 전용
2. worker 역할: 스케줄러/큐 소비/스캔 실행 전용
3. 기존 단일 모드와 하위 호환 유지

이 단계만 완료해도 멀티 워커 확장을 위한 구조적 기반이 마련됩니다.

---

## 2. 범위

### 2.1 In Scope

1. 환경변수 기반 역할 분기 도입
2. 앱 부팅 경로에서 역할별 컴포넌트 초기화 분기
3. 시작 로그에 역할 및 활성 컴포넌트 명시
4. 배포 템플릿에 역할별 실행 예시 추가

### 2.2 Out of Scope

1. 큐 외부화(DB-backed queue)
2. 상태 저장소 외부화
3. 스케줄러 영속성/리더 선출

---

## 3. 설계 요약

### 3.1 신규 환경변수

1. APP_ROLE
- 값: web | worker | all
- 기본값: all
- 의미:
  - web: 웹 서비스만 활성
  - worker: 백그라운드 작업만 활성
  - all: 기존 동작(하위 호환)

2. ENABLE_SCHEDULER
- 값: 0 | 1
- 기본값: APP_ROLE에 따라 자동 결정
- 의미:
  - 명시 시 APP_ROLE보다 우선

3. ENABLE_SCANNER_QUEUE_WORKER
- 값: 0 | 1
- 기본값: APP_ROLE에 따라 자동 결정
- 의미:
  - 큐 소비 워커 스레드 활성 여부

권장 정책:
- 운영에서는 APP_ROLE을 반드시 명시
- all은 로컬 개발/긴급 롤백 전용

### 3.2 역할별 활성 매트릭스

1. APP_ROLE=web
- Flask API: ON
- APScheduler: OFF
- ScannerQueue worker loop: OFF

2. APP_ROLE=worker
- Flask API: ON 또는 경량 health endpoint만 ON (초기 구현은 ON 허용)
- APScheduler: ON
- ScannerQueue worker loop: ON

3. APP_ROLE=all
- Flask API: ON
- APScheduler: ON
- ScannerQueue worker loop: ON

초기 구현 가이드:
- 호환성을 위해 worker에서도 앱 생성은 유지
- 실제 트래픽 라우팅은 배포 레벨에서 web만 노출

---

## 4. 코드 변경 설계

## 4.1 core.py

변경 포인트:
1. 환경변수 파서 유틸 추가
2. 역할 계산 함수 추가
3. 스케줄러 시작부 조건 분기
4. 시작 로그 출력

의사코드:

```python
role = os.getenv("APP_ROLE", "all").strip().lower()
enable_scheduler = resolve_flag("ENABLE_SCHEDULER", role in ("worker", "all"))
enable_queue_worker = resolve_flag("ENABLE_SCANNER_QUEUE_WORKER", role in ("worker", "all"))

if enable_queue_worker:
    import services.scanner_queue  # worker thread starts

if enable_scheduler:
    from services.scheduler_service import SchedulerService
    SchedulerService.start_scheduler()
```

주의:
- scanner_queue는 import 시 worker thread가 시작되는 구조이므로, import 타이밍을 role 분기 내부로 이동 필요

## 4.2 services/scanner_queue.py

변경 포인트:
1. 모듈 import 시 자동 인스턴스 생성 동작 유지하되, 생성 시 worker loop 활성 플래그 반영
2. worker loop 비활성 모드에서도 enqueue/get_queue_status는 동작 가능하도록 유지

권장 방식:
- `_init_queue(start_worker=True)` 형태로 확장
- `start_worker=False`이면 큐 자료구조만 유지

## 4.3 services/scheduler_service.py

변경 포인트:
1. start_scheduler() 호출 시 중복 가드 강화
2. 비활성 모드에서 start 요청이 오면 no-op 로그만 남기고 반환

---

## 5. 배포 변경 설계

### 5.1 Docker Compose 권장 분리

1. web 서비스
- APP_ROLE=web
- 포트 외부 노출

2. worker 서비스
- APP_ROLE=worker
- 포트 외부 비노출
- 동일 볼륨/db 공유

예시 개념:

```yaml
services:
  bookoasis-web:
    environment:
      - APP_ROLE=web
    ports:
      - "5930:5930"

  bookoasis-worker:
    environment:
      - APP_ROLE=worker
    ports: []
```

### 5.2 Non-Docker(systemd) 권장

1. bookoasis-web.service
- APP_ROLE=web

2. bookoasis-worker.service
- APP_ROLE=worker

---

## 6. 영향도 및 난이도

1. 영향도: 상
- 부팅/실행 경로가 바뀌므로 운영 영향 큼

2. 구현 난이도: 중
- 코드량은 크지 않으나, import side-effect 제어가 핵심 난점

3. 예상 공수
- 개발: 1일
- 스테이징 검증: 0.5~1일
- 운영 반영: 0.5일

---

## 7. 테스트 체크리스트

### 7.1 기능 검증

1. APP_ROLE=web
- API 정상 응답
- 스캔 스케줄 자동 실행 없음
- 큐 worker thread 미기동 확인

2. APP_ROLE=worker
- 스케줄러 기동 확인
- 큐 소비 동작 확인
- 스캔 트리거 정상 수행

3. APP_ROLE=all
- 기존 단일 모드와 동일 동작

### 7.2 회귀 검증

1. 수동 스캔 API 트리거 후 정상 수행
2. cancel-scan 정상 반영
3. 상태 API 응답 정상

### 7.3 장애 검증

1. worker 프로세스 재시작 후 스케줄 재등록 중복 없음
2. web만 살아있는 상황에서 스캔이 자동 실행되지 않음(의도된 동작)

---

## 8. 롤백 시나리오

1. 즉시 롤백
- APP_ROLE=all로 되돌림
- ENABLE_SCHEDULER=1, ENABLE_SCANNER_QUEUE_WORKER=1 강제

2. 점진 롤백
- worker 서비스 중지
- web 단일 서비스로 복귀

---

## 9. 완료 기준 (Phase 1 DoD)

1. web/worker 분리 배포에서 기능 회귀 없이 24시간 이상 안정 동작
2. worker 2개 미만 구성에서 스케줄 중복 실행이 발생하지 않음
3. 역할별 시작 로그에 활성 컴포넌트가 명시됨
4. APP_ROLE=all에서 기존 동작 100% 호환

---

## 10. Phase 2 인계 항목

Phase 2에서 바로 착수할 수 있도록 아래를 인계합니다.

1. 큐 상태 테이블 초안 DDL
2. 상태 전이 규약(queued/running/success/failed/cancelled)
3. 중복 dequeue 방지 전략(원자적 업데이트 조건)

이 문서는 메이저 로드맵의 Phase 1 구현 기준 문서로 사용합니다.

## 11. 실행 티켓 분해 문서

1. Phase 1 실행 티켓 분해
- [roadmap_worker_role_separation_phase1_task_breakdown.md](./roadmap_worker_role_separation_phase1_task_breakdown.md)
