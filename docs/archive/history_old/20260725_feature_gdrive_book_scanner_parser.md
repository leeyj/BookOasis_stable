---
title: "구글 드라이브 원격 공유 폴더 도서 수집 스캐너 파서 (Google Drive API & Scraper Fallback) 개발"
category: "feature"
date: 2026-07-25
severity: "medium"
affected_files:
  - "utils/drive_helper.py"
  - "tools/scanner/engine.py"
tags: [gdrive_scanner, fetch_gdrive_folder_files, gdrive_api, web_scraper_fallback, feature]
---

# 🚀 기능 개발 내역: 구글 드라이브 원격 폴더 도서 수집 파서 구현

## 개요

구글 드라이브 웹 공유 링크 카테고리 스캔 시, 구글 드라이브 REST API(또는 공개 웹 파싱 폴백)를 호출하여 해당 폴더 내의 도서 파일들(ZIP, CBZ, EPUB, PDF, TXT 등)의 목록과 메타데이터를 수집해 DB(`books` 및 `series`)에 감지·등록하도록 스캐너 파서 엔진을 확장함.

---

## 주요 구현 사항

1. **구글 드라이브 파일 목록 수집기 ([utils/drive_helper.py](file:///c:/project/media_server/utils/drive_helper.py))**:
   - `extract_gdrive_folder_id(path)`: URL에서 구글 드라이브 Folder ID 추출.
   - `fetch_gdrive_folder_files(folder_id)`:
     - 1차: Google Drive REST API (`gdrive_api_key` 기반 `files.list`) 호출.
     - 2차: 공개 웹 페이지 스크래핑 정규식 파싱 폴백 (무로그인 공개 링크용).

2. **스캐너 멀티스레드 엔진 연동 ([tools/scanner/engine.py](file:///c:/project/media_server/tools/scanner/engine.py))**:
   - `_scan_library_internal`에서 `is_gdrive_url(t_path)` 감지 시 `fetch_gdrive_folder_files`를 호출하여 원격 가상 경로(`gdrive://{folder_id}`) 기반으로 도서 목록 및 태스크 큐 형성.

---

## 검증 결과

- Python 구문 검사(`python -m py_compile`) 통과.
- `python deploy.py`를 통해 서버 배포 완료. 구글 드라이브 카테고리 스캔 시 원격 도서 파일들이 정상 감지되어 서재에 등록됨.
