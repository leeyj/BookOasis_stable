---
title: "CSP 단계 전환 체크리스트"
project: "BookOasis"
category: "checklist"
date: 2026-08-03
tags: [security, csp, rollout, checklist]
---

# CSP 단계 전환 체크리스트 (Report-Only -> Enforce)

이 문서는 BookOasis의 CSP 적용을 운영 중단 없이 단계적으로 전환하기 위한 점검표입니다.

---

## 1. 사전 조건

1. 서버가 `Content-Security-Policy-Report-Only` 헤더를 반환하고 있어야 합니다.
2. CSP 리포트 수집 엔드포인트가 활성화되어 있어야 합니다. (`POST /api/security/csp-report`)
3. 리포트 파일 저장 경로가 유효해야 합니다. (기본: `logs/csp_reports.jsonl`)
4. 최소 3일 이상 실제 사용자 트래픽에서 리포트를 수집해야 합니다.

---

## 2. 환경 변수 기준값 (권장)

```env
SECURITY_CSP_ENABLED=true
SECURITY_CSP_REPORT_ONLY=true
SECURITY_CSP_ENFORCE=false
SECURITY_CSP_LOG_REPORTS=true
SECURITY_CSP_REPORT_FILE=./logs/csp_reports.jsonl
SECURITY_CSP_REPORT_RATE_LIMIT_PER_MIN=120
SECURITY_CSP_REPORT_DEDUP_WINDOW_SEC=30
```

운영 부하가 큰 경우:
1. `SECURITY_CSP_REPORT_RATE_LIMIT_PER_MIN`을 낮춥니다. (예: 60)
2. `SECURITY_CSP_REPORT_DEDUP_WINDOW_SEC`를 늘립니다. (예: 60)

---

## 3. Report-Only 관측 단계 점검

1. 홈(`/`)과 로그인(`/login`) 포함 주요 페이지 응답 헤더에 `Content-Security-Policy-Report-Only`가 있는지 확인합니다.
2. 서버 로그 또는 `logs/csp_reports.jsonl`에 `[CSP-REPORT]` 또는 JSONL 레코드가 누적되는지 확인합니다.
3. 24시간 이상 관측 시 아래 항목을 집계합니다.
   - `effective_directive`
   - `blocked_uri`
   - `source_file`
4. 동일 이벤트의 반복 폭주가 없는지 확인합니다.

판정 기준:
1. 분당 억제(suppressed) 요약이 지속적으로 과도하지 않을 것
2. 브라우저/OS 특정 노이즈를 제외한 실제 기능 영향 위반이 식별될 것

---

## 4. 정책 보정 순서

1. 위반 상위 `blocked_uri`가 내부 정적 자산인지 외부 자산인지 분리합니다.
2. 내부 자산 위반은 경로/로딩 방식 버그를 먼저 수정합니다.
3. 외부 자산 위반은 실제 필요성 검토 후 최소 허용 원칙으로 도메인을 추가합니다.
4. `script-src`에서 불필요한 예외(`unsafe-eval`, 광범위 https 허용 등)를 즉시 제거하지 말고 단계적으로 축소합니다.

---

## 5. Enforce 전환 체크

아래 조건을 모두 만족하면 전환합니다.

1. 최근 48시간 동안 치명적 기능 차단 위반이 없음
2. 로그인, 라이브러리, 뷰어, 설정, 플러그인 UI 핵심 경로 수동 점검 완료
3. 운영자 롤백 절차 문서화 완료

전환값:

```env
SECURITY_CSP_REPORT_ONLY=false
SECURITY_CSP_ENFORCE=true
```

---

## 6. 롤백 절차

문제 발생 시 즉시:

```env
SECURITY_CSP_ENFORCE=false
SECURITY_CSP_REPORT_ONLY=true
```

적용 후:
1. 서버 재시작
2. 문제 요청 재현
3. 새 위반 레코드 확인 후 정책 재보정

---

## 7. 운영 권장사항

1. 프런트엔드 리소스 구조 변경 릴리스마다 24시간 Report-Only 재관측
2. 플러그인 UI/외부 스크립트 경로 변경 시 사전 검증
3. 월 1회 `csp_reports.jsonl` 상위 위반 리포트 점검
