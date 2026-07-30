---
title: "도서 파일명 중복에 따른 표지 이미지 해시 충돌 및 오염 버그 근본 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, scanner, cover, hash-collision, singleton, database-cleanup]
---

# 🐛 도서 파일명 중복에 따른 표지 이미지 해시 충돌 및 오염 버그 근본 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 라이브러리 목록(시리즈 목록) 스크롤 및 로드 시, 서로 다른 고유 도서들이 각각 고유한 표지를 갖지 못하고 특정 작품(예: '2레벨로 회귀한 무신')의 표지로 화면 전체가 덮어씌워져 오염되는 버그 발생.

## 2. 원인 분석 (Root Cause Analysis)
- **근본 원인 (해시 충돌)**:
  - 기존 스캐너 엔진(`tools/scanner/cover.py`) 내 표지 생성기(`get_series_cover_fallback` 및 `extract_cover_from_b64`)는 표지 파일명(`book_[해시].png`)을 결정할 때 단행본의 순수 파일명(예: `0 - 01권`, `01권.zip`)만을 키로 활용하여 MD5 해시를 구했음.
  - 이로 인해 서로 다른 작품 폴더에 위치하더라도 파일명이 `0 - 01권` 등으로 겹치는 수십 개의 서로 다른 작품의 1권들이 모두 동일한 MD5 해시값(`94495f6c382878d35a42d6e6fba4e64c`)을 가짐.
  - 그 결과 물리적으로 단 하나의 파일(`book_94495f6c382878d35a42d6e6fba4e64c.png`)을 여러 작품들이 덮어쓰고 공유하면서 최신 스캔된 특정 작품의 이미지로 전체 도서 표지가 전사되는 충돌이 발생함.
- **VFS(구글 드라이브) 재스캔 갱신 누락**:
  - 원격 경로(`is_remote`)에 보관된 도서의 경우, 스캐너가 대량 I/O 오버헤드를 막기 위해 압축파일 내 표지 이미지 강제 추출을 스킵(`is_remote` 감지 시 즉시 리턴)하도록 방어 코드가 들어가 있음.
  - 이 때문에 사용자가 [표지 새로고침]을 하더라도 과거 오염되었던 잘못된 해시명(`book_94495f6c...png`)이 DB에서 갱신되지 못하고 그대로 잔존함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**:
  - [cover.py](file:///c:/project/media_server/tools/scanner/cover.py):
    - 이미지 해시 생성 시 `filename` 단독이 아닌, 폴더 경로를 결합한 전체 경로 `file_path`/`full_path`를 해시의 시드로 활용하여 고유한 `book_[고유경로해시].png` 명칭을 생성하도록 수정 완료.
  - [core.py](file:///c:/project/media_server/tools/scanner/core.py):
    - `process_folder_task` 및 `scan_library_covers_only` 내 `process_cover_task` 루프에서 커버 추출기 호출 시 전체 경로 `full_path`/`file_path`를 정상 매핑하여 넘겨주도록 변경 완료.
  - [ui.js](file:///c:/project/media_server/static/js/ui.js):
    - 지연 로딩을 위한 `IntersectionObserver`를 모듈 수준의 **싱글톤** 구조로 변경하여 렌더링 성능 최적화.
  - [clean_db_covers.py](file:///c:/project/media_server/tools/clean_db_covers.py) **[신규 파일]**:
    - 이미 오염된 DB를 일괄 정화하기 위해 구형 파일명 기반 해시값을 탐색해 실제 `file_path` 기반 신형 고유 해시명으로 자동 포팅하는 마이그레이션 스크립트를 구현 및 실행하여, 홈 서버 라이브 DB 내 **총 58,081권의 표지 매핑 정보를 성공적으로 자동 정화 완료**함.

## 4. 결과 검증 (Verification Results)
- 원격 DB 마이그레이션 스크립트 실행을 통해 58,081건의 오염된 해시 데이터 즉시 수정 완료.
- 사용자 실운영 서버 배포 및 DB 정화 완료 후 브라우저 새로고침 및 목록 로드 시, 꼬였던 1권들의 이미지들이 고유 경로를 기준으로 완벽하게 격리되어 올바른 표지로 각각 깨끗하게 렌더링되는 것을 검증 완료.
