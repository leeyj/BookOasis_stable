---
title: "1 컨테이너 2 프로세스 (웹/워커 분리) 실행 계획서 - 코드 기준 개정판"
description: "현재 코드 구조(Gunicorn + Flask + scanner_queue)에 맞춰, 웹과 스캐너 큐를 프로세스 분리하는 실구현 계획"
date: 2026-07-14
---

# 1. 목적
스캔 작업(디스크 I/O + 메타 파싱 + DB 쓰기)과 웹 요청 처리(대시보드/API/뷰어)를 같은 파이썬 런타임에서 함께 수행하면서,
스캔 중 UI 지연/타임아웃(예: 524 체감)이 발생한다.

본 문서는 "도커 1컨테이너" 유지 조건에서
웹 서버와 큐 워커를 프로세스 단위로 분리해 응답성을 개선하는 실구현 계획을 제시한다.

핵심 원칙:
- 외부 큐(Redis/Celery) 도입 없이 진행
- 기존 scanner_queue 동작 모델 유지
- 단계적 전환(롤백 용이)

# 2. 현재 구조 요약 (As-Is)
- 웹 런타임: Gunicorn이 core:app 실행
- 큐/워커: services/scanner_queue.py 내부 스레드 워커
- 대기열 API: /api/media/system/queue가 같은 프로세스 메모리(scanner_queue 객체) 직접 조회
- 스케줄러: core import 시 SchedulerService.start_scheduler() 호출

문제 포인트:
- 웹 요청 처리와 스캔 실행이 같은 런타임 자원을 공유
- 스캔 부하 시 웹 응답성 저하

# 3. 목표 구조 (To-Be)
단일 컨테이너 내부에서 두 프로세스를 동시에 구동한다.

- Web Process (외부 노출)
  - 포트: 5930
  - 책임: 사용자 HTTP 요청 처리
  - 스캔 관련 요청은 Worker Internal API로 프록시

- Worker Process (내부 전용)
  - 포트: 5931 (컨테이너 외부 미노출)
  - 책임: scanner_queue 소유, enqueue/상태조회/취소 수행, 실제 스캔 실행

통신 방식:
- Web -> Worker: http://127.0.0.1:5931/internal/*

# 4. 중요한 구현 제약
이번 코드베이스에서는 core.py 내부 multiprocessing 분기보다,
엔트리포인트에서 2프로세스를 명시적으로 기동하는 방식이 안정적이다.

이유:
- 현재 운영은 Gunicorn 기반이며 core import 시 부수효과(스케줄러 시작)가 존재
- Gunicorn 워커/시그널 모델과 앱 내부 multiprocessing 혼합 시 종료/재기동 제어가 불안정해질 수 있음

# 5. 단계별 작업 계획

## Phase 1. Worker Internal API 신설
신규 파일:
- services/worker_app.py

구현 항목:
- Flask/FastAPI 중 경량 구현체 1개 선택
- 엔드포인트:
  - POST /internal/scan
  - GET /internal/status
  - POST /internal/cancel
  - POST /internal/clear
- 내부 인증:
  - 헤더 기반 내부 토큰(X-Internal-Token) 검증
  - 토큰은 환경변수 INTERNAL_WORKER_TOKEN 사용

핵심:
- 이 프로세스가 scanner_queue singleton을 "유일 소유"하도록 구성

## Phase 2. Web API 프록시 전환
수정 파일:
- api/routes/system_routes.py
- services/scheduler_service.py (필요 시)

수정 항목:
- /api/media/system/queue, /clear, /cancel에서 scanner_queue 직접 접근 제거
- Worker Internal API 호출로 교체
- 에러 처리 표준화:
  - Worker down -> 503 + 사용자 친화 메시지
  - timeout -> 504 맵핑

추가 권장:
- 내부 호출 타임아웃(예: 2초) + 재시도 1회

## Phase 3. 스캔 트리거 경로 통일
수정 파일 후보:
- api/routes/library_routes.py
- services/scheduler_service.py
- (필요 시) api/routes/system_routes.py webhook 경로

목표:
- 스캔 등록 지점을 Worker enqueue API 하나로 수렴
- Web 프로세스에서 scanner_queue 직접 호출 0건 달성

## Phase 4. 컨테이너 실행 모델 변경
수정 파일:
- entrypoint.sh
- Dockerfile

실행 전략:
- entrypoint.sh가
  1) worker_app.py 백그라운드 실행
  2) gunicorn(core:app) 실행
  3) SIGTERM/SIGINT 수신 시 두 프로세스 모두 종료

중요:
- Dockerfile EXPOSE는 5930만 유지 (5931은 내부 통신 전용)

## Phase 5. 관측성/검증
추가 항목:
- Worker health endpoint (/internal/health)
- 로그 태그 구분: [WEB], [WORKER], [QUEUE]
- 대시보드 경고: Worker 비정상 시 "스캔 기능 일시 중단" 안내

# 6. 성공 기준 (KPI)
아래를 동일 환경에서 비교 측정한다.

- KPI-1: 스캔 중 /api/system/status P95 응답시간
  - 목표: 기존 대비 30% 이상 개선
- KPI-2: 스캔 중 대시보드 진입 실패율(5xx/524)
  - 목표: 기존 대비 유의미 감소
- KPI-3: 큐 상태 조회 API 실패율
  - 목표: 1% 미만

# 7. 리스크 및 대응

1) SQLite write 경합
- 리스크: Worker와 Web의 동시 DB 쓰기 경쟁
- 대응: WAL 유지 + 대량 쓰기 청크 커밋 + busy timeout 일관화

2) 프로세스 생명주기 관리
- 리스크: Worker만 남거나 Web만 남는 비정상 상태
- 대응: entrypoint에서 trap 기반 동시 종료/재기동 처리

3) 내부 API 장애 전파
- 리스크: Worker down 시 스캔 관련 UI 장애
- 대응: 프록시에서 503 반환 + 운영 로그 경보 + health 체크

4) 메모리 사용량 증가
- 리스크: 프로세스 분리로 baseline RAM 증가
- 대응: 허용 예산 수립(예: +50~120MB), 운영 모니터링

# 8. 롤아웃 전략
1. 기능 플래그 추가
- ENABLE_WORKER_PROCESS=true/false

2. 배포 순서
- 1차: 코드 반영 + 플래그 false (비활성 배포)
- 2차: 스테이징에서 플래그 true 검증
- 3차: 운영 일부 구간 활성화

3. 롤백
- 플래그 false 즉시 전환으로 단일 프로세스 경로 복귀

# 9. 작업 체크리스트
- [ ] services/worker_app.py 생성
- [ ] internal auth 토큰/헤더 검증 구현
- [ ] system_routes queue API를 worker 프록시로 전환
- [ ] 스캔 enqueue 경로 단일화
- [ ] entrypoint 2프로세스 기동 및 trap 종료 구현
- [ ] Dockerfile/문서 포트 정책 정리
- [ ] KPI 측정 스크립트/로그 기준 확정
- [ ] 플래그 기반 롤아웃/롤백 검증

# 10. 결론
이 계획은 현재 코드베이스에서 실현 가능하다.
다만 "core.py multiprocessing 직접 분기" 대신
"entrypoint 프로세스 오케스트레이션 + internal API 프록시" 경로가
운영 안정성과 롤백 용이성 측면에서 더 적합하다.

