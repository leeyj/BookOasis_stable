---
id: "20260623_bugfix_remote_path_cover_pages"
date: 2026-06-23
category: "bugfix"
severity: "high"
status: "fixed"
tags: [lazy_scanner, cover, total_pages, gdrive, ux]
---

# 20260623 — 원격 경로(GDRIVE) 도서 커버·페이지 수 누락 버그 수정

## 버그 내역

### 현상
카테고리 18의 "고기로 츄 [마나베 조지]" 시리즈(총 8화)에서 다음 두 가지 문제가 동시에 발생:

1. **커버 이미지 누락**: 3화~8화의 `cover_image`가 `NULL`
2. **페이지 수 0**: 전 화(1화~8화) `total_pages=0`, `has_offsets=0`
3. **뷰어 오동작**: 1화 뷰어에서 세로 레이아웃 깨짐, 페이지 수 오표시
4. **사용자 인지 불가**: 어떤 화면에도 경고가 없어 사용자가 원인을 알 수 없음

### 근본 원인
파일 경로가 `/home/.../GDRIVE/...`를 포함해 `is_remote_path()` → `True` 판정:

| 위치 | 결과 |
|------|------|
| `tools/scanner/core.py` | `is_remote=True` → 오프셋 수집 스킵 → `total_pages=0` |
| `tools/scanner/cover.py` | `is_remote=True` → Fallback 커버 추출 차단 → 3화~8화 `NULL` |
| `tools/lazy_scanner.py` | 타겟 조건: 커버 없는 경우만 → 1·2화(커버 있음, pages=0) 영구 스킵 |

## 영향도

| 영향 항목 | 범위 |
|-----------|------|
| 커버 누락 | GDRIVE 경로 도서 중 kavita.yaml 미포함 파일 전체 |
| total_pages=0 | GDRIVE 경로 ZIP/CBZ 도서 전체 |
| 뷰어 오동작 | has_offsets=0 도서 열람 시 Fast Path 비활성, 레이아웃 깨짐 가능 |
| 사용자 인지 불가 | 상세 화면에 어떤 경고도 없어 혼란 유발 |

## 수정 사항

### 수정 파일 목록

#### `tools/lazy_scanner.py`
- `_collect_zip_offsets_safe()` 헬퍼 함수 신규 추가
- DB 조회 쿼리에 `total_pages`, `has_offsets`, `file_format` 컬럼 추가
- 타겟 조건 확장: ZIP/CBZ이고 `total_pages=0` OR `has_offsets=0`인 경우도 재처리 대상 포함
- `get_series_cover_fallback_single()` 모든 반환지점을 3-튜플 `(cover, meta, offsets)`로 확장
- `run_lazy_cover_extraction()`: 3-튜플 언패킹 후 오프셋 DB 저장(`save_book_offsets`) 추가
- 커버 추출 실패해도 오프셋이 있으면 단독 저장(total_pages 복구)

#### `services/book_detail_service.py`
- SELECT 쿼리 2곳에 `b.has_offsets` 추가
- `books_list` 응답 딕셔너리에 `has_offsets` 항목 추가

#### `static/js/modal.js`
- `volumesHtml` 렌더링 루프에 스캔 오류 감지 로직 추가
  - ZIP/CBZ이고 `total_pages=0` OR `has_offsets=0` → 경고 배너 표시
  - `cover_image` 없음 → "커버 미검출" 경고 추가
- `rescanBook(event, bookId, seriesName, libraryId)` 함수 신규 추가
  - `/api/media/books/{id}/scan` 단일 재스캔 API 호출
  - 완료 후 상세 화면 자동 새로고침

#### `static/css/style.css`
- `.vol-warn-banner`: 노란색 계열 경고 배너 스타일
- `.btn-rescan-book`: 재스캔 버튼 스타일 (비활성화 상태 포함)

## 해결 사항

### 백엔드
- Lazy Scanner 실행 시 원격 경로 도서의 `total_pages`, `has_offsets`가 자동으로 채워짐
- 1화·2화처럼 커버는 있지만 페이지 수가 0인 경우도 자동 감지 후 처리

### 프론트엔드
```
시리즈 상세 화면 진입
├─ total_pages=0 화 → ⚠️ "페이지 수 미검출 — 정상 열람이 어려울 수 있습니다." 배너 표시
├─ 커버 없는 화 → ⚠️ "커버 미검출" 배너 표시
└─ [↻ 다시 스캔] 버튼 → 단일 재스캔 → 완료 후 자동 새로고침 → 배너 사라짐
```

### 설계 유지 사항
- `tools/scanner/core.py` 및 `tools/scanner/cover.py`의 원격 차단 로직은 유지
  (대량 스캔 시 OOM/I/O 폭주 방지 의도적 설계)
- Lazy Scanner가 원격 파일 처리의 유일한 책임 주체로 명확히 분리됨
