---
title: "Phase 1 실행 티켓 분해 문서"
project: "BookOasis"
category: "roadmap"
date: 2026-07-12
tags: [roadmap, phase1, execution, tickets, worker]
---

# Phase 1 실행 티켓 분해 문서

## 1. 목적

이 문서는 Phase 1 상세 설계를 실제 구현 작업 단위로 분해한 실행 문서입니다.
각 티켓은 독립 배포 가능성을 기준으로 설계했습니다.

---

## 2. 전제 조건

1. 운영 환경에서 APP_ROLE 주입 방식이 확정되어야 함
2. 현재 단일 모드(all) 동작이 정상임을 확인해야 함
3. 롤백 경로(APP_ROLE=all 복귀)를 사전 검증해야 함

---

## 3. 티켓 목록

## T1. 역할 플래그 파서 도입

목표:
- 공통 플래그 해석 유틸을 추가해 분기 로직을 단순화

변경 대상:
1. core.py

작업 항목:
1. APP_ROLE 해석 함수 추가 (web, worker, all)
2. bool 플래그 해석 함수 추가 (0/1, true/false)
3. 시작 로그에 role/flag 출력

완료 기준:
1. 잘못된 값 입력 시 안전 기본값(all) 적용
2. 시작 로그에 role 값이 명시됨

난이도: 하
영향도: 중
예상: 0.5일

---

## T2. core 부팅 경로 역할 분기

목표:
- 부팅 시 scheduler/queue worker 활성 여부를 역할 기반으로 결정

변경 대상:
1. core.py

작업 항목:
1. ENABLE_SCHEDULER 기본값을 role 기반으로 산정
2. ENABLE_SCANNER_QUEUE_WORKER 기본값을 role 기반으로 산정
3. scheduler start 호출을 조건부 처리
4. scanner_queue import 지점을 조건부 처리

완료 기준:
1. APP_ROLE=web에서 scheduler 미기동
2. APP_ROLE=worker에서 scheduler 기동
3. APP_ROLE=all에서 기존과 동일 동작

난이도: 중
영향도: 상
예상: 0.5~1일

---

## T3. scanner_queue 무작동 모드 지원

목표:
- 큐 객체는 유지하되 worker loop만 비활성 가능한 구조 도입

변경 대상:
1. services/scanner_queue.py

작업 항목:
1. worker thread 시작 여부를 생성 인자로 제어
2. 비활성 모드에서도 enqueue, get_queue_status, clear_queue 동작 유지
3. 시작 로그에 worker loop 상태 출력

완료 기준:
1. worker loop OFF일 때 스레드가 생성되지 않음
2. API에서 queue status 호출 시 오류 없음

난이도: 중
영향도: 상
예상: 1일

---

## T4. scheduler start 중복 가드 강화

목표:
- 잘못된 호출 또는 중복 부팅에서 scheduler 재기동을 방지

변경 대상:
1. services/scheduler_service.py

작업 항목:
1. start_scheduler idempotent 보장
2. 비활성 모드 start 요청 시 no-op 처리
3. 중복 시 경고 로그 추가

완료 기준:
1. start_scheduler 다회 호출 시 단일 인스턴스 유지
2. web 역할에서는 start 요청이 무시됨

난이도: 중
영향도: 중
예상: 0.5일

---

## T5. 역할별 상태 API 검증 보강

목표:
- web/worker/all에서 상태 API가 예측 가능한 응답을 반환하도록 검증

변경 대상:
1. api/routes/system_routes.py
2. 테스트 또는 점검 스크립트(선택)

작업 항목:
1. role별 queue 상태 노출 형태 점검
2. 비활성 queue worker 상황 문구 점검
3. 예외 케이스 로그 정리

완료 기준:
1. APP_ROLE=web에서 상태 API 500 없음
2. APP_ROLE=worker에서도 상태 API 일관성 유지

난이도: 하
영향도: 중
예상: 0.5일

---

## T6. 배포 템플릿 업데이트

목표:
- docker/systemd 기준으로 web/worker 분리 실행 예시 제공

변경 대상:
1. docker-compose.override.example.yml 또는 문서
2. docs/guide_installation.md
3. docs/guide_installation_en.md

작업 항목:
1. web 서비스 APP_ROLE=web 예시 추가
2. worker 서비스 APP_ROLE=worker 예시 추가
3. 롤백 절차 문구 추가

완료 기준:
1. 운영자가 문서만으로 역할 분리 실행 가능
2. 롤백 절차가 명시됨

난이도: 하
영향도: 중
예상: 0.5일

---

## T7. 통합 검증 및 스테이징 런북

목표:
- 스테이징에서 Phase 1 변경을 안정 검증

변경 대상:
1. docs/ 내부 런북 문서

작업 항목:
1. APP_ROLE=web 단독 실행 검증
2. APP_ROLE=worker 단독 실행 검증
3. web+worker 동시 실행 검증
4. APP_ROLE=all 롤백 검증

완료 기준:
1. 24시간 동안 중복 스케줄/중복 스캔 없음
2. 주요 API 오류율 증가 없음

난이도: 중
영향도: 상
예상: 1~2일

---

## 4. 작업 순서(권장)

1. T1
2. T2
3. T3
4. T4
5. T5
6. T6
7. T7

총 예상 기간:
- 개발 + 검증 최소 4~6일
- 운영 반영 포함 6~8일

---

## 5. 리스크와 완화책

1. 리스크: 역할 설정 누락으로 worker 미동작
- 완화: 시작 로그에 role/active components 강제 출력

2. 리스크: import side-effect로 queue worker가 의도치 않게 기동
- 완화: scanner_queue import를 조건부로 제한

3. 리스크: 스케줄러 중복 start
- 완화: idempotent 가드 + 중복 감지 로그

---

## 6. 체크리스트

배포 전:
1. APP_ROLE=all 회귀 테스트 통과
2. role별 부팅 로그 확인
3. 롤백 시나리오 리허설 완료

배포 후:
1. 상태 API 오류율 모니터링
2. 스캔 작업 중복 실행 여부 점검
3. 524 및 5xx 지표 비교

---

## 7. 연계 문서

1. 메이저 로드맵
- ./roadmap_worker_role_separation_major_patch.md

2. Phase 1 상세 설계
- ./roadmap_worker_role_separation_phase1_detailed_design.md
