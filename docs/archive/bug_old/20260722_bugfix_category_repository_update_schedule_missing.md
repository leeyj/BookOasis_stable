---
title: "CategoryRepository 내 update_schedule 메서드 누락 결함 해결"
category: "bugfix"
date: 2026-07-22
severity: "high"
affected_files:
  - "repositories/sqlite/category_repository.py"
  - "api/routes/library_routes.py"
tags: [category_repository, schedule, bugfix]
---

# CategoryRepository 내 update_schedule 메서드 누락 결함 해결

## 1. 결함 원인 분석
- 웹 UI의 **[라이브러리 주기 스케줄 등록/수정]** 기능 수행 시, API 엔드포인트(`api/routes/library_routes.py`)에서 `CategoryRepository.update_schedule(db_type, library_id, cron_val, vfs_refresh, rclone_rc_url)`을 호출하도록 작성되었으나, 데이터 액세스 레이어인 `CategoryRepository` 클래스에 해당 정적 메서드가 정의되어 있지 않아 `type object 'CategoryRepository' has no attribute 'update_schedule'` AttributeError 오류가 발생하던 현상을 확인했습니다.

## 2. 주요 수정 사항
- **[repositories/sqlite/category_repository.py](file:///c:/project/media_server/repositories/sqlite/category_repository.py)**
  - `@staticmethod`로 `update_schedule(db_type, library_id, cron_schedule, vfs_refresh_before_scan, rclone_rc_url)` 메서드를 구현.
  - 해당 라이브러리의 `cron_schedule`, `vfs_refresh_before_scan`, `rclone_rc_url` 컬럼 값이 데이터베이스에 안전하게 업데이트되도록 추가.

## 3. 검증 결과
- 라이브러리 스케줄 등록 및 주기 변경 시 DB 반영과 크론(Cron) 스케줄러 등록이 에러 없이 정상적으로 수행됨을 확인함.
