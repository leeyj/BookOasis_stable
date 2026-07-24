---
title: "메타데이터 잠금(metadata_locked) 식별 녹색 자물쇠 표시 및 상세 뷰 잠금해제 기능 추가"
category: "feature"
date: 2026-07-23
affected_files:
  - "repositories/sqlite/series_repository.py"
  - "services/series_service.py"
  - "repositories/sqlite/book_repository.py"
  - "api/library.py"
  - "static/js/api.js"
  - "static/js/tab_media_library.js"
  - "static/js/modal.js"
tags: [metadata_locked, indicator, unlock, UI, feature]
---

# 🚀 기능 구현 내역: 메타데이터 잠금(`metadata_locked`) 식별 녹색 자물쇠 표시 및 상세 뷰 잠금해제 기능 추가

## 1. 개요 및 요구사항
- **배경**: 사용자가 도서 메타데이터를 수동 편집하거나 플러그인을 적용하면 `metadata_locked = 1` 상태가 되어 메타데이터가 잠기지만, 화면에서 잠김 여부를 파악할 수 없고 DB 수동 편집 없이는 해제할 수 없는 불편함이 존재했음.
- **요구사항**:
  1. 시리즈/도서 카드 커버 이미지 좌측 하단에 **녹색 자물쇠 아이콘 배지**를 그려 visual하게 식별되도록 조치.
  2. 도서 상세 리스트 화면에서 `[정보 수정]` 옆에 **`[잠금해제]` 버튼 추가** (단, `metadata_locked = 1` 로 잠긴 항목에 한해서만 노출).
  3. `[정보 수정]` 편집 시에는 자동으로 잠김(`metadata_locked = 1`) 유지.

## 2. 주요 변경 사항 (Architectural Changes)
1. **백엔드 메타데이터 잠금 상태 전달 및 해제 API**:
   - `SeriesRepository.fetch_books_for_grouping` & `SeriesService._build_series_entries`: 시리즈 엔트리에 `metadata_locked` 필드(시리즈 내 권 중 1개라도 잠겨있으면 1) 추가.
   - `BookRepository.unlock_metadata`: `UPDATE books SET metadata_locked = 0 WHERE (series_name = ? AND library_id = ?) OR id = ?` 해제 쿼리 구현.
   - `POST /api/media/unlock-metadata`: 메타데이터 잠금 해제 라우트 엔드포인트 구축.

2. **프론트엔드 UI 렌더링**:
   - `tab_media_library.js`: 시리즈/도서 그리드 카드 커버 좌측 하단에 `<div class="locked-badge" ...><i class="fa-solid fa-lock" style="color:#22c55e;"></i></div>` 표시.
   - `modal.js`: 상세 모달 헤더에서 `metadata_locked === 1` 인 경우 `[정보 수정]` 버튼 바로 옆에 `[잠금해제]` 버튼 렌더링 및 해제 API 연동.

## 3. 검증 결과
- 정적 구문 검증 완료 및 `[잠금해제]` 클릭 시 즉시 `metadata_locked = 0` 원복 및 자물쇠 배지 소거 동작을 확인.
