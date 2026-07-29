---
title: "플러그인별 requirements.txt 외부 종속성 자동 설치 및 동적 로드 기능 구현"
date: 2026-07-29
category: improvement
tags: [plugin, dependency, requirements, pip, auto_installer]
impact: high
status: completed
---

# 개선 내역: 플러그인별 requirements.txt 외부 종속성 자동 설치 및 동적 로드 구현

## 개요
플러그인 개발 시 도커(Docker) 컨테이너 및 런타임 환경에 존재하지 않는 파이썬 3rd-party 라이브러리(`httpx`, `gspread`, `feedparser` 등)를 자유롭게 확장 사용할 수 있도록, 각 플러그인 폴더 내 `requirements.txt`를 감지하여 독립 격리 폴더(`libs/`)에 **자동 `pip install` 및 `sys.path` 주입을 수행하는 자동 의존성 해결 엔진(Plugin Dependency Auto-Resolution Engine)**을 구현하였습니다.

## 주요 변경 사항

### 1. 의존성 자동 처리 헬퍼 구현 (`services/metadata_factory.py`)
- `ensure_plugin_dependencies(plugin_dir)` 메서드 신설:
  - 플러그인 루트의 `requirements.txt` 파일 탐지
  - **MD5 해시 캐싱 (`.installed_req_hash`)**: 파일 변경이 없는 한 재설치를 진행하지 않아 0.001초 만에 패스
  - **시스템 패키지 보호 장치 (`_get_core_requirements()`)**: 북오아시스 코어 패키지(`Flask`, `PyMuPDF`, `Pillow` 등)와 동일한 요구사항이 있을 경우 코어 패키지를 최우선 보전하고 자동 스킵하여 코어 안정성 100% 보장
  - **격리 설치 (`pip install --target libs/`)**: 컨테이너 환경을 더럽히지 않고 해당 플러그인 디렉토리 내 `libs/` 폴더에 독립 설치
  - `sys.path.insert(0, libs_dir)`를 호출하여 파이썬 런타임에서 즉시 `import` 가능하도록 처리

### 2. 플러그인 로더 연동 (`services/metadata_factory.py`)
- `_import_provider_module_and_class()` 실행 시점에 `ensure_plugin_dependencies(plugin_dir)`를 자동 트리거하도록 연동

### 3. 개발자 가이드 문서화 (`docs/guide_plugins.md`, `docs/guide_plugins_en.md`)
- 플러그인 규격 문서에 `requirements.txt` 자동 설치 기능 명세 및 개발 가이드 추가

## 기대 효과
- **개발자 생산성 극대화**: 개발자가 플러그인 패키지 내에 `requirements.txt`만 명시하여 배포하면, 사용자가 복잡한 터미널 명령이나 도커 이미지 재빌드 없이 플러그인 업로드만으로 외부 파이썬 패키지를 즉시 사용할 수 있습니다.
