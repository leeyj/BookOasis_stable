---
title: "Flask Blueprint 중첩 구조에 따른 url_for 빌드 에러 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-22
tags: [bugfix, flask, blueprint, routing]
---

# 🐛 Flask Blueprint 중첩 구조에 따른 url_for 빌드 에러 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 세션 로그인 기능 탑재 후 서비스 접속 시, `/login` 페이지로 리다이렉션하는 과정에서 Flask의 URL 맵 어댑터가 엔드포인트를 찾지 못하고 아래의 `BuildError` 크래시를 유발함.
  ```text
  werkzeug.routing.exceptions.BuildError: Could not build url for endpoint 'auth.login'. Did you mean 'media_api.auth.login' instead?
  ```

## 2. 원인 분석 (Root Cause Analysis)
- `api/__init__.py` 하이브리드 아키텍처에 따라, `auth_bp`가 독자적으로 루트에 붙지 않고 통합 `media_api` Blueprint 내부에 중첩 등록(`api_bp.register_blueprint(auth_bp)`)되어 있음.
- 중첩 구조의 Blueprint 하위 핸들러들은 URL 매핑 시 부모 Blueprint의 이름인 `media_api`가 접두사로 함께 바인딩되어 `media_api.auth.login`이 최종 엔드포인트 명칭이 됨.
- 코드 상에서 구형 규격인 `url_for('auth.login')`으로 직접 조회하여 발생한 논리 에러임.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [auth.py](file:///c:/project/media_server/api/auth.py)
  - 미인증 시 리다이렉션 타겟 및 예외 경로 허용 리스트에 선언되어 있던 `url_for('auth.login')` 구문 4군데를 모두 중첩 구조의 명칭인 **`url_for('media_api.auth.login')`**으로 일괄 개정함.

## 4. 결과 검증 (Verification Results)
- 소스 코드 수정 후 서버 재구동 시, `/` 접속을 시도하면 더이상 크래시(500)가 나지 않고 로그인 템플릿 페이지인 `/login`으로 안전하게 포워딩되어 렌더링되는 것을 최종 확인 완료함.
