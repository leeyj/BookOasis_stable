---
title: "동일 시리즈명 타 카테고리 표지 혼용 버그 추가 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-23
tags: [bug, backend, series_service, cover_image, library_id]
---
# 버그 내역
서로 다른 카테고리(예: '잡지', '만화(완결A)')에 동일한 이름의 시리즈가 존재할 때, 메인 리스트나 그리드 뷰에서 한 카테고리의 도서가 다른 카테고리의 표지를 빌려와 노출하는 버그 발견. (예: 잡지의 '행복이 가득한 집'이 만화 카테고리의 '행복이 가득한 집' 표지를 표시) 상세페이지에 진입하면 정상적으로 표시됨.

# 원인
이전 버그 조치(`duplicate_series_category_mapping`)에서 클릭 시 상세 뷰 진입을 위한 `library_id` 매핑 오류는 수정되었으나, `SeriesService`에서 도서 목록을 불러오는 SQL 쿼리 내 커버 이미지 서브 쿼리는 여전히 `series_name`에만 의존하여 조회하고 있었음. 이로 인해 동일 시리즈명이 존재할 경우 먼저 검색된 타 카테고리 도서의 표지가 반환됨. 또한, `GROUP BY` 구문이 `series_name` 단일 기준이어서 전체 보관함('all') 뷰에서 서로 다른 카테고리의 동일 명칭 시리즈가 하나의 항목으로 병합되는 논리적 오류가 내재되어 있었음.

# 수정 사항
1. `c:\project\media_server\services\series_service.py` : `get_books_list` 및 `get_all_books_list` 내의 모든 목록 조회 쿼리 수정.
   - `GROUP BY` 구문에 `b.library_id`를 추가하여 각 카테고리별로 동일 시리즈명이 별도로 표시되도록 물리적 분리 달성.
   - 커버 이미지 및 업데이트 일자를 가져오는 서브쿼리의 `WHERE` 절에 `AND b2.library_id = b.library_id` 조건을 추가하여 표지 썸네일 반환 시 정확한 카테고리 일치 보장.

# 해결 사항
- 이제 각 카테고리에 있는 동명의 시리즈가 자신에게 맞는 올바른 표지를 정확하게 렌더링함.
- 전체 리스트('all') 뷰에서도 서로 다른 카테고리의 동명 시리즈가 분리되어 노출됨.
