---
title: Walkthrough - sqlite_non_constant_default_migration
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# SQLite 비상수 기본값 마이그레이션 오류 조치 (Walkthrough)

SQLite 데이터베이스에서 컬럼을 추가할 때 동적인 기본값(`CURRENT_TIMESTAMP`)을 직접 할당할 수 없는 엔진 제약으로 인해 `cover_updated_at` 컬럼 마이그레이션이 실패하여 생기던 런타임 오류를 완벽하게 조치하였습니다.

## 변경 사항 요약 (Changes)

### 데이터베이스

#### [MODIFY] [database.py](file:///c:/project/media_server/database.py)
- **마이그레이션 기법 우회**: SQLite 제약 조건(`Cannot add a column with non-constant default`)을 우회하기 위해 `ALTER TABLE books ADD COLUMN cover_updated_at DATETIME`으로 컬럼을 생성한 뒤, `UPDATE books SET cover_updated_at = CURRENT_TIMESTAMP`를 순차 실행하는 방식으로 변경했습니다.

## 검증 결과 (Verification Results)
- 수정본을 원격 홈 서버에 배포 완료하고 서버를 재구동했습니다.
- 원격지 데이터베이스 `media_general.db` 및 `media_adult.db` 양측 모두에 `cover_updated_at` 컬럼이 정상적으로 추가되고 마이그레이션 작업이 완료됨을 최종 교차 검증했습니다.
