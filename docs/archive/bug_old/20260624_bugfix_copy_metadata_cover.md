---
title: "유사 메타데이터 복사 시 커버 이미지 의도치 않게 변경되는 버그 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-06-24
tags: [metadata, copy_metadata, cover_image, sql, modal]
---

# 버그 내역

도서 상세 페이지의 "유사 메타데이터 가져오기 → 이 정보로 채우기" 기능 적용 시,
텍스트 메타 정보(저자, 출판사, 줄거리 등)뿐 아니라 커버 이미지까지 원본 도서의 이미지로 교체되는 문제.

# 원인 분석

`services/metadata_service.py`의 `copy_metadata()` 메서드에서 SQL UPDATE 쿼리에
`cover_image` 컬럼도 함께 포함되어 있었음.

```sql
-- 버그 코드 (수정 전)
SELECT author, publisher, summary, link, score, cover_image
FROM books WHERE id = ?

UPDATE books
SET author = ?, publisher = ?, summary = ?, link = ?, score = ?,
    cover_image = COALESCE(NULLIF(?, ''), cover_image)   -- ← 커버가 원본 것으로 교체됨
WHERE series_name = ? AND library_id = ?
```

원본 도서(source)에 cover_image가 있을 경우, 타겟 시리즈의 모든 볼륨 커버가 원본 커버로 일괄 덮어씌워짐.

# 영향도

- **영향 범위**: 상세 뷰의 유사 메타데이터 추천 적용 기능
- **심각도**: High — 기존 커버 이미지가 무단 교체되어 사용자 수동 편집 커버까지 소실될 수 있음

# 수정 사항

**파일**: `services/metadata_service.py` (copy_metadata 메서드, Line 31~62)

```diff
- SELECT author, publisher, summary, link, score, cover_image
+ # 커버 이미지는 제외하고 순수 텍스트 메타 정보만 가져옴
+ SELECT author, publisher, summary, link, score
  FROM books WHERE id = ?

- SET author = ?, publisher = ?, summary = ?, link = ?, score = ?,
-     cover_image = COALESCE(NULLIF(?, ''), cover_image)
+ # 커버 이미지(cover_image)는 건드리지 않고 텍스트 메타 정보만 업데이트
+ SET author = ?, publisher = ?, summary = ?, link = ?, score = ?
  WHERE series_name = ? AND library_id = ?
```

# 해결 사항

유사 메타데이터 적용 시 author, publisher, summary, link, score 텍스트 필드만 업데이트되며,
커버 이미지(cover_image)는 항상 기존 값이 유지됨.
