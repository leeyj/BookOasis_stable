---
title: "구글 드라이브 공유 링크 연동 및 카테고리 추가 모달 UI/UX (카테고리 유형 분리) 개발"
category: "feature"
date: 2026-07-25
severity: "low"
affected_files:
  - "templates/components/modals/library_modal.html"
  - "static/js/category.js"
  - "static/i18n/ko.json"
  - "static/i18n/en.json"
  - "api/routes/library_routes.py"
  - "api/library.py"
  - "api/helpers/validation.py"
tags: [category_type, gdrive_link, library_modal, UI_UX_redesign, feature]
---

# 🚀 기능 개발 내역: 구글 드라이브 공유 링크 연동 및 카테고리 추가 모달 UI/UX 개발

## 개요

기존 서버 물리 디렉토리 경로 등록 카테고리 외에, 구글 드라이브 웹 공유 링크(`https://drive.google.com/drive/folders/...`)를 직접 카테고리로 연동할 수 있도록 **카테고리 유형(Category Type)**을 분리 선택하는 스마트 UI/UX 및 백엔드 연결 검증 API를 구축함.

---

## 주요 구현 사항

1. **카테고리 추가/수정 모달 UI/UX 스마트 전환 ([library_modal.html](file:///c:/project/media_server/templates/components/modals/library_modal.html))**:
   - 모달 최상단에 `[카테고리 유형]` 세그먼트 탭 버튼 추가 (`[로컬 / 마운트 경로]` vs `[구글 드라이브 공유 링크]`).
   - 유형 선택에 따라 입력창 라벨, placeholder, 우측 조작 버튼(`[📂 찾아보기]` ↔ `[⚡ 링크 연결 테스트]`), 체크박스 가시성이 동적으로 스마트하게 교체됨.

2. **구글 드라이브 공유 링크 연결 테스트 API ([api/library.py](file:///c:/project/media_server/api/library.py))**:
   - `POST /api/category/test-gdrive-links` 엔드포인트를 추가하여 입력된 웹 링크에서 구글 드라이브 Folder ID 감지 및 0.1초 연결 테스트 수행.

3. **입력 경로 유효성 검증 예외 격리 ([api/helpers/validation.py](file:///c:/project/media_server/api/helpers/validation.py))**:
   - `category_type == 'gdrive'` 일 경우 서버 로컬 디렉토리 검증(`os.path.exists`)을 우회하도록 처리.

4. **다국어 사전 갱신 ([ko.json](file:///c:/project/media_server/static/i18n/ko.json), [en.json](file:///c:/project/media_server/static/i18n/en.json))**:
   - `category_type_label`, `type_local`, `type_gdrive`, `gdrive_path_label`, `btn_test_gdrive_link` 등 다국어 번역 키 등록.

---

## 검증 사항

- 모달에서 `[구글 드라이브 공유 링크]` 선택 시 UI가 깔끔하게 전환되고 `[⚡ 연결 테스트]` 기능이 정상 동작함.
- `python deploy.py`를 실행하여 원격 서버 배포 및 미디어 서버 재기동을 이상 없이 수행함.
