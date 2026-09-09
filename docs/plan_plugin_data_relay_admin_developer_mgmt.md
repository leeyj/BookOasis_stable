# Plugin Data Relay — Admin 다중 계정 + 개발자 관리 화면 + 삭제/재등록 정책

## 배경
`plugin_data_relay`(신규 fly.io 앱, `bo-plugin-relay`)는 BookOasis 플러그인 개발자가 웹에서 스스로 계정을 만들고 최대 5개 필드를 정의하면 SQLite 테이블이 자동 생성되는 릴레이 서비스로, 게임 플러그인 리더보드 등에 쓰기 위해 구축됐다. 1차 구현(개발자 계정 분리 `/regi_user` + `/register`, 관리자 승인 게이트, SQL 인젝션 방지)까지는 이미 완료·배포됨. 이 문서는 그 다음 단계로 논의된 **admin 다중 계정, 개발자 자기관리 화면, 삭제/재등록 정책**을 구현 전에 정리한 것.

## 현재 상태 (2026-09-09 기준, 이미 배포됨)
- `POST /regi_user` — 개발자 계정 자기등록 (developer_id + 자동발급 developer_secret)
- `POST /register` — developer_id+secret 인증 필요, plugin_id + 필드(최대 5개) 등록 → `plugin_data_<id>` 테이블 자동 생성, plugin은 `status='pending'`
- `/admin` — 단일 `ADMIN_PASSWORD` 세션 로그인, 플러그인별 승인/거부 버튼
- 필드명 화이트리스트(`id`/`user_id`/`created_at` 등 고정 컬럼과 충돌 방지 포함), 스키마는 등록 시점에 고정, 변경 미지원

## 이번에 추가 논의된 것

### 1. Admin 다중 계정 (3개)
- 계정: **owner(본인) / community(커뮤니티 관리자) / tier1_dev(검증된 1티어 플러그인 개발자)**
- **권한은 3명 완전 동일** — 승인/거부/강제삭제 등 모든 관리자 기능을 동일하게 사용 가능. 계정을 나누는 이유는 권한 차등이 아니라 **누가 승인/삭제했는지 감사(audit)를 위한 구분**.
- 로그인 방식: 계정별 아이디+비밀번호 → 세션 쿠키 (지금 `/admin/login`과 동일한 방식, `ADMIN_PASSWORD` 단일값 대신 계정별 자격증명).
- **동시 접속 제한 없음** — 3명이 각자 로그인해서 동시에 작업 가능 (싱글톤 세션 아님).
- 구현 방향: `ADMIN_PASSWORD` 환경변수 하나 → `admins` 테이블(admin_id, password_hash)로 전환. 3개 계정은 자기등록이 아니라 수동 프로비저닝(초기 시딩 스크립트 또는 fly secrets를 통한 초기값 설정) — 개발자 계정처럼 오픈 셀프서비스가 아님.

### 2. 개발자 자기관리 화면
- developer_id + developer_secret으로 로그인/인증 → 본인이 등록한 plugin_id 목록, 각 상태(승인대기/승인/거부), 필드 스키마, 사용자 수/레코드 수 확인.
- `/admin` 대시보드를 필터링한 축소판 개념 (본인 것만 보임).

### 3. 삭제 정책
- **삭제 권한**: 개발자 본인(자기 plugin만) + admin(전체, 강제삭제) 모두 가능.
- **삭제 확인**: 실수 방지를 위해 **plugin_id를 다시 타이핑**해야 삭제 실행 (단순 확인 버튼 아님).
- **삭제 범위**: cascade로 완전 삭제 — `plugin_data_<id>` 동적 테이블, `plugin_fields`, `plugin_users`, `plugins` 행까지 전부 제거. 즉 해당 플러그인을 쓰던 모든 최종 사용자(플레이어)의 데이터가 통째로 사라짐 — 이건 의도된 동작.

### 4. 재등록 정책
- 삭제 후 같은 plugin_id로 다시 등록하면 **완전히 처음부터** (다시 `status='pending'`) 절차를 밟는다. 이전 이력/승인 상태를 이어받지 않음.

### 5. 스키마 변경 미지원 원칙 (재확인)
- ALTER TABLE 등 스키마 마이그레이션 기능은 **원칙적으로 만들지 않는다** (혼란 방지가 목적).
- 필드 구성을 바꾸고 싶으면 예외 없이: **삭제 → 재등록**. 즉 스키마 변경은 항상 기존 사용자 데이터 전량 삭제를 수반.

## 구현 시 참고할 기존 코드 (변경 대상)
- `plugin_data_relay/database.py` — `ADMIN_PASSWORD` 검증 로직을 대체할 `admins` 테이블/함수, plugin 삭제용 cascade 함수 추가 필요
- `plugin_data_relay/app.py` — `/admin/login`을 계정별 로그인으로 변경, 개발자 대시보드 라우트 추가, 삭제 라우트(개발자용/admin용) 추가
- `plugin_data_relay/templates/admin.html` — 로그인한 admin_id 표시(감사 목적), 삭제 버튼(+타이핑 확인 UI) 추가
- 신규 템플릿: 개발자 대시보드 페이지, 삭제 확인 모달/폼

## 다음 세션 진행 순서 (제안)
1. `admins` 테이블 설계 + 시딩 방법 확정 (fly secrets vs 관리 스크립트)
2. 삭제 API (`DELETE /api/dev/plugins/<plugin_id>`, `DELETE /admin/plugins/<plugin_id>`) 구현 + cascade 테스트
3. 개발자 대시보드 라우트/템플릿 구현
4. 로컬 전체 회귀 테스트 후 fly.io 재배포
