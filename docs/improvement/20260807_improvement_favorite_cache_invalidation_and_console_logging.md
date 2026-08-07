---
title: "즐겨찾기 카테고리 캐시 무효화 및 상세 진단 프론트엔드/백엔드 콘솔 로그 추가"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [favorite, logging, cache_invalidation, console, series_service]
---

# 🚀 [개선] 즐겨찾기 카테고리 캐시 무효화 및 상세 진단 프론트엔드/백엔드 콘솔 로그 추가

## 1. 개요
- **목적**: 기존 백엔드 `_ALL_BOOKS_CACHE`가 이전 빈 결과(`[]`)를 5분간 캐싱하고 있거나 유저별 즐겨찾기 캐시 분리가 누락되어 발생한 잔여 캐시 문제를 해결하고, 즐겨찾기 진입 시 프론트엔드 콘솔(`console.log`)에 상세 호출 로그를 출력하도록 개선함.

## 2. 주요 개선 내용 (수정 소스 파일)

### 1) [`c:\project\media_server\services\series_service.py`](file:///c:/project/media_server/services/series_service.py)
- `get_all_books_list`에서 `favorite` 카테고리 조회 시 글로벌 공유 캐시에서 제외하거나 유저별 키(`user:{user_id}:{db_type}:favorite`)로 적용되도록 분기.

### 2) [`c:\project\media_server\api\routes\book_routes.py`](file:///c:/project/media_server/api/routes/book_routes.py)
- `toggle_book_favorite` 및 `toggle_series_favorite_api` 호출 성공 시 `SeriesService.invalidate_all_books_cache()`를 실행하여 기존 렌더링 캐시 즉시 무효화.

### 3) [`c:\project\media_server\static\js\book_list.js`](file:///c:/project/media_server/static/js/book_list.js)
- `loadBooksList()` 진입, API 호출(`fetchAllBooksList`), 수신 데이터 개수 등에 `[Book-List]` 프리픽스의 상세 `console.log` 출력 구문 추가.

## 3. 검증 결과
- 홈 서버 배포(`python deploy.py`) 완료 (Server PID: 737890 / Worker PID: 737949).
- 브라우저 F12 개발자 도구 콘솔에서 `[Book-List]` 로그가 실시간 출력되어 데이터 바인딩 과정을 정밀 모니터링 가능함.
