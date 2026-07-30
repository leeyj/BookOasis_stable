---
title: "독립 CLI 카테고리 내보내기/가져오기 도구 구현"
category: "feature"
date: 2026-07-23
severity: "low"
affected_files:
  - "tools/export_category.py"
  - "tools/import_category.py"
  - "docs/guide_category_migration.md"
tags: [cli, export, import, migration, backup, feature]
---

# 독립 CLI 카테고리 내보내기/가져오기 도구 구현

## 1. 개발 배경 및 목적
- 카테고리(라이브러리) 데이터를 타 서버/시스템으로 이관하거나 백업/복구할 때, 알라딘 API 재검색이나 뷰어 offset 재계산 없이 메타데이터와 커버 이미지를 초고속으로 이관할 수 있는 전용 CLI 스크립트 개발.
- 웹서버 프로세스 점유 및 HTTP 타임아웃을 완전 차단하기 위해 독립 파이썬 CLI 방식으로 설계.

## 2. 주요 구현 내용
- **[tools/export_category.py](file:///c:/project/media_server/tools/export_category.py)**:
  - 카테고리 DB 메타데이터(`libraries`, `books`, `book_offsets`)와 수집된 커버 이미지 파일들을 `manifest.json`, `metadata.json`과 함께 `.oasis.zip` 패키지로 아카이빙.
- **[tools/import_category.py](file:///c:/project/media_server/tools/import_category.py)**:
  - `.oasis.zip` 패키지를 수신 시스템의 DB 및 파일 시스템으로 복원.
  - PK/FK Auto-Increment ID 재할당 및 수신 시스템의 새로운 마운트 경로(`--target-path`)와 상대 경로(`relative_path`)를 결합하여 `physical_path` 100% 자동 재구성.
  - 커버 이미지 파일 복사 및 `book_offsets` 일괄 복원.
- **[docs/guide_category_migration.md](file:///c:/project/media_server/docs/guide_category_migration.md)**:
  - 상세 예시와 사용법을 담은 사용자 가이드 문서 작성.

## 3. 검증 결과
- `python -m py_compile tools/export_category.py tools/import_category.py` 정적 검증 통과.
- `python tools/export_category.py --help` 및 `python tools/import_category.py --help` CLI 도움말 및 인자 파싱 정상 동작 검증 완료.
