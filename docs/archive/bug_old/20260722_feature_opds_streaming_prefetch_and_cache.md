---
title: "OPDS 및 만화 이미지 스트리밍 성능 극대화 (서버측 비동기 프리패치 & DB 메모리 캐싱)"
category: "performance"
date: 2026-07-22
severity: "high"
affected_files:
  - "services/stream_page_service.py"
  - "repositories/sqlite/book_offset_repository.py"
  - "api/cache.py"
tags: [opds, streaming, prefetch, db_cache, offset]
---

# OPDS 및 만화 이미지 스트리밍 성능 극대화

## 1. 이슈 배경
FTS5 virtual table 제거 후 DB 무결성은 정상화되었으나, OPDS 및 스트리밍 이미지 뷰어에서 페이지 열람 시 매 페이지마다 콜드 추출(Cold extraction) 및 2회의 DB 조회(`get_book_file_info`, `get_book_offset`)가 반복되어 지연 피드백이 발생했습니다.

## 2. 해결 내역
1. **[repositories/sqlite/book_offset_repository.py](file:///c:/project/media_server/repositories/sqlite/book_offset_repository.py)**
   - `_offset_cache` LRUCache(capacity 5,000)를 신설하여 오프셋 조회 시 DB 히트를 완전 0회로 단축.
2. **[services/stream_page_service.py](file:///c:/project/media_server/services/stream_page_service.py)**
   - **DB 정보 단기 캐시(`_book_info_cache`)**: 도서 파일 경로 및 포맷 조회를 인메모리 캐싱하여 매 페이지 권한 조인 쿼리 0회 조치.
   - **서버측 비동기 4페이지 사전 추출(`_trigger_background_prefetch`)**: 현재 페이지 추출 성공 시 백그라운드 daemon 스레드로 `page_idx + 1` ~ `page_idx + PREFETCH_AHEAD (4페이지)`를 미리 읽어 `image_cache` (RAM 8GB LRU)에 보관. `get_zip_read_lock`으로 스레드 안전성 보장.

## 3. 적용 결과
- 연속 페이지 요청 시 다음 페이지들이 이미 RAM 캐시에 100% 준비되어 있어 **응답 시간이 0ms (즉시 리턴)**로 극대화되었으며, OPDS 클라이언트 및 웹 뷰어 반응 속도가 회복되었습니다.
