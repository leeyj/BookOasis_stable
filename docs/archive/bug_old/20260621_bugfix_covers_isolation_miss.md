---
title: "단일 도서 스캔 및 수동 매칭 시 표지 이미지 라이브러리 격리 누수 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [bug, scanner, backend, cover]
---

# 🐛 단일 도서 스캔 및 수동 매칭 시 표지 이미지 라이브러리 격리 누수 조치

## 1. 버그 내역 및 증상
- **증상**: "이 책 즉시 스캔" 혹은 "도서 메타데이터 검색 매칭" 시 다운로드/추출된 책 표지 이미지(.png) 파일이 원래 계획된 카테고리별 격리 폴더인 `covers/{library_id}/`에 저장되지 않고, 공용 최상위 디렉터리인 `covers/` 바로 하위에 누출 생성되는 버그 발생.

## 2. 영향도
- **영향 범위**: 표지 파일 관리 체계 및 다중 라이브러리 간 표지 관리의 격리성 보존 저해.
- **우선순위**: 중

## 3. 원인 분석
1. **단일 도서 스캔 (`services/book_scan_service.py`)**:
   - `extract_cover_from_b64` 및 `get_series_cover_fallback` 호출 시, 책의 카테고리 식별값인 `library_id` 매개변수를 인자로 넘겨주지 않아 `None`으로 작동하였고, 이로 인해 헬퍼 함수 내부에서 디폴트 저장소인 `COVERS_DIR` (최상위 covers/)로 바로 표지를 적재함.
2. **알라딘 메타데이터 수동 매칭 (`plugins/metadata/aladin.py`)**:
   - `apply()` 함수가 DB에서 `file_path`와 `series_name`만 조회하고 `library_id`를 누락했으며, 표지를 다운로드할 때 `covers` 폴더의 최상위만 획득해 직접 파일을 저장함. DB의 `cover_image` 컬럼 경로도 격리 접두사(`{library_id}/`) 없이 순수 파일명만 입력되어 저장됨.

## 4. 조치 사항
- **수정 소스 파일**:
  1. `services/book_scan_service.py` (단일 도서 스캔 시 표지 헬퍼 호출 파라미터 보완)
  2. `plugins/metadata/aladin.py` (DB library_id 추가 쿼리 및 격리 디렉터리 저장 경로 구성)
- **조치 내용**:
  - `book_scan_service.py`의 69라인 및 72라인에 각각 `library_id=library_id` 인자를 명시하여 표지가 `covers/{library_id}` 폴더에 격리 저장되도록 조치했습니다.
  - `aladin.py`의 `apply()` 함수 내 DB 검증 쿼리에 `library_id` 컬럼 조회를 추가하고, 이미지 저장 디렉터리를 `os.path.join(base_dir, 'covers', str(library_id))` 로 튜닝했습니다. 또한 DB에 쓰이는 파일 명칭 경로도 `{library_id}/book_{hash}.png` 형태로 격리 적재되도록 보완했습니다.

## 5. 해결 사항 및 검증 결과
- 로컬 개발본 소스 수정을 완료했습니다.
- **주의 (배포 보류)**: 현재 원격 서버에서 실시간 스캔이 백그라운드로 진행되고 있으므로, 안정성을 위해 원격 배포(`deploy.py`) 및 Gunicorn 단독 재시작은 스캔 완료 시점 이후에 수동으로 진행하도록 배포를 보류하였습니다.
