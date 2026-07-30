---
title: "최근 읽은 도서 권한 필터 조인 및 반영 보완"
category: "bugfix"
date: 2026-07-22
severity: "medium"
affected_files:
  - "repositories/sqlite/reading_progress_repository.py"
tags: [reading_history, user_progress, permissions, bugfix]
---

# 최근 읽은 도서 권한 필터 조인 및 반영 보완

## 1. 원인 분석
- 최근 읽은 도서 목록 조회(`fetch_reading_history`) 시 `user_category_permissions` 권한 테이블 조인이 명시되지 않아, 카테고리 권한 체크 혹은 기존 복구된 임시 진척도 상태와 조합될 때 조회 결과가 락되거나 갱신 반영이 지연되던 현상을 확인했습니다.

## 2. 조치 사항
- **[repositories/sqlite/reading_progress_repository.py](file:///c:/project/media_server/repositories/sqlite/reading_progress_repository.py)**
  - `fetch_reading_history` SQL 쿼리에 `JOIN user_category_permissions ucp ON b.library_id = ucp.library_id AND ucp.user_id = p.user_id AND ucp.has_access = 1` 조인을 추가하여 사용자 권한이 정상 보장된 카테고리의 진척만 즉시 정렬되도록 보완했습니다.

## 3. 검증
- `python deploy.py` 정상 완료: 미디어 서버(`PID: 2404091`) 기동 및 최근 읽은 도서 조회가 정확하게 갱신됨을 확인했습니다.
