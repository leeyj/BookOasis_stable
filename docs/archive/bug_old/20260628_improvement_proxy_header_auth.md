---
title: "Proxy Header Auth (SSO) 설정 추가"
project: "BookOasis"
category: "general"
date: 2026-06-28
tags: [improvement, auth, security]
---

## 🚀 개선 내역 (Improvement)
- 리버스 프록시(Authentik, Authelia 등) 환경에서 `Remote-User` 또는 `X-Forwarded-User` 헤더를 통해 비밀번호 입력 없이 BookOasis에 자동 로그인할 수 있는 기능(SSO)을 추가했습니다.
- 일반 사용자의 보안 사고를 방지하기 위해 해당 기능은 기본적으로 비활성화(Off)되어 있으며, 어드민의 **일반 설정** 메뉴에서 수동으로 활성화할 수 있도록 UI를 추가했습니다.

## 🛠 수정 사항
- **백엔드 (API)**:
  - `api/auth.py` 의 `check_authentication()` 함수에 프록시 헤더 확인 및 자동 세션 발급 로직을 구현했습니다.
  - 보안상 `SettingsService.get('PROXY_HEADER_AUTH')` 값이 `'1'` 일 때만 작동하도록 안전장치를 마련했습니다.
- **프론트엔드 (UI & JS)**:
  - `templates/components/views/library_settings.html` 파일에 해당 기능을 제어하는 셀렉트박스와 강력한 주의 문구(보안 경고)를 삽입했습니다.
  - `static/js/settings/general.js` 에 해당 옵션의 데이터를 불러오고 저장하는 로직을 연동했습니다.

## ⚠️ 영향도 및 보안 유의사항
- 외부망에 직접 BookOasis를 개방한 상태에서 이 옵션을 활성화할 경우, 누구나 임의의 헤더를 주입해 관리자로 로그인할 수 있는 심각한 취약점이 될 수 있습니다.
- 반드시 로컬망 내부 혹은 Nginx 등 리버스 프록시 뒤에서만 활성화해야 합니다.
- 기존의 아이디/비밀번호 기반 로그인 방식에는 전혀 영향을 주지 않습니다.
