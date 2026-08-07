---
title: "MariaDB 모드 db_path 식별자 정비 - SQLite 파일 경로 로그 혼선 제거"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [mariadb, db_path, logging, identifier, scheduler, scan_routes]
---

# 🚀 [개선] MariaDB 모드 db_path 식별자 정비 - SQLite 파일 경로 로그 혼선 제거

## 1. 개요
- **문제**: MariaDB 모드 구동 시 스캐너/스케줄러 태스크 로그에 SQLite 파일 경로(`/home/az001a/Script/media_server/db/media_general.db`)가 그대로 노출되어, 실제 MariaDB를 사용하는데 SQLite를 쓰는 것처럼 보이는 혼선이 발생함.
- **원인**: `database.get_db_path()`가 MariaDB 모드에서도 항상 SQLite 파일 경로를 리턴하였고, 각 라우트/스케줄러에서 이 파일 경로를 큐 kwargs나 로그에 그대로 전달함.

## 2. 수정 상세 내용 (수정 소스 파일)

### 1) [`c:\project\media_server\database.py`](file:///c:/project/media_server/database.py)
- `is_mariadb_mode()` 헬퍼 함수 추가.
- `get_db_path(db_type)`: MariaDB 모드일 경우 `mariadb:media_general`, `mariadb:media_adult`, `mariadb:media_audiobook` 형태의 식별자 문자열 리턴.

### 2) [`c:\project\media_server\services\scheduler_service.py`](file:///c:/project/media_server/services/scheduler_service.py)
- `auto_resume_interrupted_jobs()` 및 `reload_all_jobs()`의 `os.path.exists(db_path)` 체크를 MariaDB 식별자(`mariadb:...`) 시 스킵하도록 분기 보완.

### 3) [`c:\project\media_server\api\routes\library_routes.py`](file:///c:/project/media_server/api/routes/library_routes.py) / [`scan_routes.py`](file:///c:/project/media_server/api/routes/scan_routes.py)
- `get_db_path_for_scan()`을 하드코딩된 SQLite 경로 대신 `database.get_db_path(db_type)` 위임으로 교체.

## 3. 결과 및 검증
- 홈 서버 배포(`python deploy.py`) 완료 (Server PID: 316059 / Worker PID: 316119).
- MariaDB 모드 스캔 로그가 `db_path='mariadb:media_general'` 형태로 출력되어 SQLite 경로와의 혼선이 100% 제거됨.
