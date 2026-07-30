---
title: "가상 라이브러리 필터링 오작동으로 인한 상세 뷰 단행본 미노출 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-19
tags: [bugfix, details, filter]
---

# 🐛 가상 라이브러리 필터링 오작동으로 인한 상세 뷰 단행본 미노출 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 최근 읽은 도서(`history`) 혹은 대시보드에서 책 카드를 눌러 상세 보기 페이지로 진입했을 때, 단행본 개수가 '0권'으로 노출되며 하단 도서 목록에 아무것도 나타나지 않는 현상.

## 2. 원인 분석 (Root Cause Analysis)
- 상세 보기 API(`get_media_detail`)는 호출 당시 프론트엔드의 `state.currentLibraryId`를 전달받아 필터링함.
- `state.currentLibraryId`가 `'history'` 등 가상/시스템 라이브러리 값일 때도 `library_id != 'all'` 분기에 의해 SQL 쿼리 조건문에 `library_id = 'history'`가 포함되어 조회 실패가 발생함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: `services/book_service.py`
- 상세 보기 시 실제 물리 라이브러리 ID 필터만 동작하도록 `use_lib_filter` 판단 로직을 수정하여 가상 라이브러리(`history`, `favorite`, `home`)를 필터링 대상에서 제외함.
  ```python
  use_lib_filter = library_id and library_id not in ('all', 'history', 'favorite', 'home')
  ```

## 4. 결과 검증 (Verification Results)
- 코드 수정 후, 최근 읽은 도서 화면 및 대시보드에서 도서 상세 카드로 진입 시 단행본 목록이 누락 없이 정상 렌더링됨을 확인함.
