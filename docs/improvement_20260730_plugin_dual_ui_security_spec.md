---
title: "플러그인 듀얼 UI 아키텍처(카테고리 뷰 vs 환경설정 폼) 분리 서빙 및 런타임 보안 제약 장치 구현"
date: 2026-07-30
category: improvement
tags: [plugin, dual_ui, security, path_traversal, settings_ui]
impact: high
status: completed
---

# 개선 내역: 플러그인 듀얼 UI 아키텍처 분리 서빙 및 런타임 보안 제약 장치 구현

## 개요
플러그인의 UI 서빙 구조를 **카테고리 메인 풀페이지 UI (`index.html`)**와 **환경설정 커스텀 폼 UI (`settings.html`)**로 2원화 분리 서빙하도록 고도화하고, `Path Traversal (../)` 차단 등 엄격한 런타임 보안 검증 및 개발 가이드 규격을 수립했습니다.

## 주요 변경 사항

### 1. 듀얼 UI 템플릿 서빙 분리 (`services/metadata_factory.py`, `static/js/settings/plugins.js`)
- **백엔드 `_load_plugin_ui_bundle(provider_name, target='view'|'settings')` 구현**:
  - `target='view'`: `index.html`, `style.css`, `script.js` 반환 (사이드바 카테고리 클릭 시 메인 뷰포트에 풀페이지 마운트)
  - `target='settings'`: `settings.html`, `settings.css`, `settings.js` 반환 (환경설정 탭 카드에 커스텀 폼 마운트)
- **프론트엔드 조건부 렌더링**:
  - `settings.html`이 존재하면 커스텀 설정 폼을 마운트하고, 존재하지 않을 경우 `config_schema` 파이썬 배열 기반 폼이 자동 생성되어 노출됨.

### 2. 강력한 런타임 보안 및 경로 검증 엔진 (`services/metadata_factory.py`)
- **`_validate_safe_plugin_path()` 및 `SecurityError` 구현**:
  - `os.path.commonpath` 검증을 통해 `plugins/metadata/{plugin_id}/` 디렉토리를 상위 탈출하는 `../` 경로 시도를 원천 차단.
  - 외부 시스템 디렉토리를 가리키는 심볼릭 링크 파일 접근 403/SecurityError 즉시 거부.
  - 외부 파이썬 라이브러리는 `libs/` 하위로 격리 설치되고 코어 패키지는 최우선 보호됨.

### 3. 개발자 가이드 규격 최신화 (`docs/guide_plugins.md`, `docs/guide_plugins_en.md`)
- 듀얼 UI 구조도 및 작성법 명시.
- 4대 보안 및 디렉토리 제약사항(Path Traversal 금지, Symlink 제한, 패키지 격리, XSS 방어 규칙) 최신화.
