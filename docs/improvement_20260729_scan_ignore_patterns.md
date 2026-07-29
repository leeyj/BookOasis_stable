---
title: "파일 및 디렉토리 스캔 제외 기능 (git-style ignore) 구현"
date: 2026-07-29
category: improvement
tags: [scanner, ignore, synology, eaDir, recycle, gitignore]
impact: high
status: completed
---

# 개선 내역: 파일 및 디렉토리 스캔 제외 기능 (git-style ignore) 구현

## 개요
시놀로지 NAS 사용 환경에서 생성되는 `@eaDir`, `#recycle` 메타데이터 디렉토리 및 사용자 임시 파일(`*.tmp`, `*.sample.cbz` 등)이 미디어 라이브러리 스캔 시 오탐으로 등록되거나 스캔 속도를 저하시키는 문제를 해결하기 위해, **git-style 형태의 스캔 제외 예외 패턴(Scan Ignore Patterns)** 기능을 구현하였습니다.

## 주요 변경 사항

### 1. 스캔 제외 모듈 신설 (`tools/scanner/ignore_filter.py`)
- `IgnoreFilter` 클래스 구현:
  - 와일드카드 패턴 (`*.tmp`, `*.sample.cbz`), 특정 폴더명 (`@eaDir`, `#recycle`), 시스템 숨김파일 (`.DS_Store`, `Thumbs.db`) 매칭 지원
  - 주석(`＃`) 처리 지원 및 `#recycle` 특수 디렉토리 예외 구분
  - 폴더별 `.bookoasisignore` 또는 `.ignore` 파일 탐지 및 동적 규칙 병합 지원

### 2. 스캐너 디렉토리 순회 최적화 (`tools/scanner/engine.py`)
- `os.walk` 탐색 시 `dirs[:] = [d for d in dirs if not ignore_filter.should_ignore_dir(d, root)]` 구문을 적용하여 **제외 대상 디렉토리의 하위 순회 자체를 물리적으로 조기 차단(Pruning)**
- 파일 수집 단계에서 `ignore_filter.should_ignore_file(f, root)`로 예외 파일 차단
- 구글 드라이브(VFS) 원격 링크 스캔 시에도 동일 필터 적용

### 3. 관리자 전역 설정 UI 및 DB 연동
- DB `settings` 테이블에 `SCAN_IGNORE_PATTERNS` 키 시드 추가
- `api/routes/settings_routes.py`에 허용 키 등록
- `templates/components/settings/general_tab.html` 및 `static/js/settings/general.js`에 "스캔 제외 패턴 (Scan Ignore Patterns)" 입력 UI 추가

### 4. 다국어(i18n) 번역 키 추가 (`ko.json`, `en.json`)
- `scan_ignore_patterns_label`, `scan_ignore_patterns_desc` 추가

## 효과 및 검증
- 시놀로지 NAS의 `@eaDir`, `#recycle` 디렉토리 하위의 수많은 미니 썸네일 이미지 및 데이터 파일들이 스캔 대상에서 물리적으로 차단되어 **스캔 시간이 획기적으로 단축**되었습니다.
- 임시 다운로드 파일(`*.tmp`) 및 샘플 파일이 라이브러리에 잘못 등록되는 현상이 근본적으로 방지되었습니다.
