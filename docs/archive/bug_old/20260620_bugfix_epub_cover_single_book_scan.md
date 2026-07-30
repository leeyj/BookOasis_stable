---
title: "개별 도서 스캔 기능 추가 및 EPUB 표지 자동 추출 Fallback 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [epub-cover, single-book-scan, contextmenu]
---

# 🧠 개별 도서 스캔 기능 추가 및 EPUB 표지 자동 추출 Fallback 조치

## 1. 개요 및 버그 내용
- **현상**:
  - `SF가 세계를 읽는 방법(개정판) [김창규].epub` 등 단일 EPUB 파일만 위치한 도서 폴더의 경우, `kavita.yaml` 메타데이터에 Base64 표지가 지정되어 있지 않으면 스캐너의 표지 추출 Fallback이 ZIP/CBZ만 대상으로 하여 작동하지 않아 기본 아이콘으로 출력되는 구조적 미흡점 발생.
  - 전체 스캔을 가동하기엔 I/O 비용 및 시간이 과다하므로 개별 책 수준에서 마우스 우클릭을 통해 단독 재스캔이 가능한 기능 구현 요구.

## 2. 원인 분석
- `tools/scanner.py` 내 `get_series_cover_fallback` 함수는 폴더 내의 `.zip` 및 `.cbz` 압축파일 목록만 탐색해 첫 이미지를 표지로 사용하도록 코딩되어 있어 `.epub` 포맷은 지원 대상에서 누락됨.
- 개별 책의 메타데이터 및 표지 갱신을 즉각 실행하는 백엔드 API 및 프론트엔드 컨텍스트 메뉴 바인딩 로직이 부재했음.

## 3. 조치 내용
1. **[scanner.py](file:///c:/project/media_server/tools/scanner.py)**:
   - `get_series_cover_fallback` 의 탐색 범위에 `.epub`를 포함.
   - `extract_epub_cover_direct` 헬퍼 함수를 설계하여 EPUB 내부 `container.xml` -> `.opf` -> `manifest` 경로를 통해 표지 이미지를 강제로 찾아 압축 해제 및 캐싱하도록 처리.
2. **[book_scan_service.py](file:///c:/project/media_server/services/book_scan_service.py) [NEW]**:
   - 단일 `book_id`에 대해 부모 폴더 메타데이터 파싱 및 표지 강제 재추출(`force=True`)을 격리 수행하는 스캔 모듈 신설.
3. **[library.py](file:///c:/project/media_server/api/library.py)**:
   - `/api/media/books/<int:book_id>/scan` POST 엔드포인트를 노출하여 단독 스캔 바인딩.
4. **[tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)** & **[tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)**:
   - `#book-context-menu` 우클릭용 마크업 및 `window.showBookContextMenu`, `window.triggerScanSingleBook` 리스너 추가.
5. **[ui.js](file:///c:/project/media_server/static/js/ui.js)** & **[modal.js](file:///c:/project/media_server/static/js/modal.js)**:
   - 도서 그리드 카드와 상세화면의 단행본 행 카드에 `contextmenu` 이벤트를 매핑하여 우클릭 메뉴가 실행되도록 바인딩.

## 4. 결과 및 검증
- 수동 검증 예정.
