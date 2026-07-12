---
title: "워커 역할 분리 메이저 패치 로드맵"
project: "BookOasis"
category: "roadmap"
date: 2026-07-12
tags: [roadmap, scanner, scheduler, worker, architecture, performance]
---

# 워커 역할 분리 메이저 패치 로드맵

## 1. 배경과 목표

현재 구조는 웹 요청 처리(API/UI)와 스캐너/스케줄러 실행이 동일 프로세스 역할에 결합되어 있습니다.
이로 인해 스캔 부하 시 웹 응답 지연(타임아웃, 524)이 발생하며, 향후 Gunicorn worker 확장 시 프로세스 간 상태 불일치 위험이 큽니다.

본 메이저 패치의 목표는 다음과 같습니다.

1. 웹 프로세스와 백그라운드 작업 프로세스의 역할을 분리한다.
2. 프로세스 로컬 메모리 상태를 공용 상태 저장소로 이관한다.
3. worker 확장 가능 구조를 확보하면서 기존 기능 회귀를 방지한다.

---

## 2. 현재 구조의 핵심 문제

1. 프로세스 로컬 큐/상태
- `services/scanner_queue.py`의 싱글톤 큐는 프로세스마다 독립 인스턴스입니다.
- 멀티 워커에서 작업 중복/상태 불일치 가능성이 큽니다.

2. 프로세스 로컬 튜닝 상태
- `services/db_tuning_service.py`의 `_tuning_status`는 메모리 딕셔너리입니다.
- 워커별로 서로 다른 상태를 보게 됩니다.

3. 스케줄러 부팅 결합
- 앱 시작 시 스케줄러를 바로 올리는 방식은 멀티 워커에서 중복 스케줄링 위험이 있습니다.

4. 스캔 부하가 웹 응답을 직접 압박
- 동일 런타임 내 CPU/GIL/DB 대기 구간 경쟁으로 웹 요청 지연이 커집니다.

---

## 3. 설계 원칙

1. 단일 책임 프로세스
- Web: HTTP 요청 처리 전용
- Worker: 스케줄링/큐 소비/스캔 실행 전용

2. 상태의 외부화
- 큐/진행상태/튜닝상태를 DB(또는 Redis) 기반으로 조회 가능하게 설계

3. 점진적 전환
- 한번에 전면 교체하지 않고 단계별로 기능 플래그를 통해 전환

4. 안전한 롤백
- 각 단계별 실패 시 즉시 구버전 동작으로 복귀 가능해야 함

---

## 4. 단계별 실행 계획 (Major Patch)

### Phase 0. 사전 계측 및 가드레일 (준비 단계)

목표:
- 변경 전/후 비교를 위한 지표 확보

작업:
1. API p95/p99 응답시간, 5xx, 524 지표 수집
2. 스캔 진행 중 상태 API 성공률, 평균 응답시간 로깅
3. 스캔 작업 중복 실행 감지 로그 강화

산출물:
- 베이스라인 성능 리포트

난이도: 하
영향도: 중
예상 기간: 0.5~1일

---

### Phase 1. 역할 게이트 도입 (웹/워커 분리 스위치)

목표:
- 프로세스 역할을 환경변수로 명시적으로 분리

작업:
1. `APP_ROLE` 도입 (`web`, `worker`)
2. `core.py`에서 역할별 초기화 분기
- `web`: API 서비스만
- `worker`: scheduler/queue 소비 활성
3. 기본값은 기존 호환 모드로 시작하되, 배포에서 명시 설정 권장

산출물:
- 단일 코드베이스에서 역할 분리 실행 가능

난이도: 중
영향도: 상
예상 기간: 1~2일
리스크:
- 역할 설정 누락 시 작업 미실행 가능
대응:
- 시작 로그에 역할/활성 컴포넌트 요약 출력

---

### Phase 2. 큐/상태 저장소 외부화

목표:
- 프로세스 로컬 상태 제거

작업:
1. 스캐너 큐 상태 저장 테이블 설계 (DB 우선)
2. `scanner_queue`를 DB-backed queue로 전환
3. 진행 단계(stage), started_at, enqueue_at, retry_count 등의 상태 컬럼 정의
4. `/api/system/status`, `/api/media/system/queue`를 공용 저장소 조회로 전환

산출물:
- 멀티 워커/멀티 프로세스에서 동일 상태 조회 가능

난이도: 상
영향도: 상
예상 기간: 3~5일
리스크:
- 큐 컨디션 레이스, 중복 dequeue
대응:
- 원자적 상태 전이(queued -> running) 쿼리 설계
- 작업 key 유니크 제약 적용

---

### Phase 3. 스케줄러 단일화

목표:
- 중복 스케줄 등록/실행 제거

작업:
1. 스케줄러는 `worker` 역할에서만 활성화
2. 웹 프로세스에서는 스케줄러 비활성
3. 부팅 시 stale running job 복구 정책 적용

산출물:
- 스케줄 중복 실행 리스크 제거

난이도: 중
영향도: 상
예상 기간: 1~2일

---

### Phase 4. 웹 워커 확장 및 운영 튜닝

목표:
- web worker 증가 가능한 구조 완성

작업:
1. Gunicorn worker 수 점진 상향 (예: 1 -> 2 -> 4)
2. 상태 API/핵심 API의 p95/p99, 오류율 모니터링
3. 스캔 처리량 및 작업 지연(큐 대기시간) 튜닝

산출물:
- worker 확장 가능한 운영 가이드

난이도: 중
영향도: 상
예상 기간: 1~2일

---

## 5. 영향도 분석

### 5.1 컴포넌트별 영향

1. 높은 영향
- `core.py` (앱 부팅/역할 분기)
- `services/scanner_queue.py` (큐 엔진)
- `services/scheduler_service.py` (스케줄 활성 조건)
- `api/routes/system_routes.py` (상태 조회 API)

2. 중간 영향
- `services/db_tuning_service.py` (튜닝 상태 외부화)
- 배포 스크립트/컨테이너 실행 정의 (`Dockerfile`, `docker-compose.yml`)

3. 낮은 영향
- 뷰어/라이브러리 비즈니스 로직 대부분

### 5.2 사용자 영향

1. 기대 효과
- 스캔 중 대시보드 응답성 개선
- 상태 API 일관성 개선
- 운영 시 worker 확장 가능

2. 잠재 부작용
- 초기 전환 구간에서 큐 처리 지연 가능
- 역할 설정 실수 시 스캐너 미실행 가능

---

## 6. 구현 난이도 요약

1. 전체 난이도: 중상
2. 핵심 난점:
- 안전한 큐 상태 전이(원자성)
- 기존 동작과의 호환 유지
- 장애 시 복구/재시도 정책 정합성

3. 인력/기간 추정 (1인 기준)
- 최소: 7~10 영업일
- 안정화 포함 권장: 10~14 영업일

---

## 7. 검증 계획 (테스트 전략)

### 7.1 기능 테스트

1. 스캔 시작/취소/재시작/자동 재개 시나리오
2. cover scan/lazy scan/library scan 큐 순서 보장
3. 상태 API 정합성 (running/pending/stage)

### 7.2 부하 테스트

1. 스캔 동작 중 대시보드 주요 API 연속 호출
2. worker 1,2,4 단계별 응답시간 비교
3. 중복 작업 enqueue 방지 검증

### 7.3 장애/복구 테스트

1. worker 프로세스 강제 종료 후 running job 복구
2. DB 락/타임아웃 상황에서 큐 무결성 확인

---

## 8. 롤백 계획

1. 플래그 기반 즉시 롤백
- `APP_ROLE` 분기 비활성화로 기존 단일 역할 모드 복귀

2. 큐 엔진 롤백
- DB-backed queue 기능 플래그 OFF 시 기존 메모리 큐로 복귀

3. 운영 롤백 순서
1. worker scale-down
2. 웹 단일 모드 복귀
3. 스케줄러 기존 경로 재활성

---

## 9. 수용 기준 (Definition of Done)

다음 조건을 모두 만족하면 완료로 간주합니다.

1. 웹 worker 2개 이상에서 중복 스캔/상태 불일치가 없다.
2. 스캔 중 `/api/system/status`와 `/api/media/system/queue`가 안정적으로 응답한다.
3. 스캔 부하 하에서도 대시보드 핵심 API 524 비율이 베이스라인 대비 유의미하게 감소한다.
4. 장애 복구 테스트(강제 종료/재기동)에서 큐 무결성이 보장된다.

---

## 10. 다음 액션 제안 (메이저 착수 전)

1. Phase 0 지표 수집을 먼저 2~3일 수행
2. 운영 환경에 `APP_ROLE` 주입 방식 확정 (`docker-compose`, systemd, k8s 중 택1)
3. 큐 외부화 저장소를 DB 우선으로 갈지 Redis 병행으로 갈지 의사결정

이 문서는 메이저 패치 착수 시 기술 설계서(LLD)의 상위 입력 문서로 사용합니다.

## 11. 연계 상세 설계 문서

1. Phase 1 상세 설계
- [roadmap_worker_role_separation_phase1_detailed_design.md](./roadmap_worker_role_separation_phase1_detailed_design.md)

2. Phase 1 실행 티켓 분해
- [roadmap_worker_role_separation_phase1_task_breakdown.md](./roadmap_worker_role_separation_phase1_task_breakdown.md)
