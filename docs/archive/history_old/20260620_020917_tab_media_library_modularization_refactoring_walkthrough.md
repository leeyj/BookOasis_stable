---
title: Walkthrough - tab_media_library_modularization_refactoring
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 라우트 레이어 모듈화 리팩토링 결과 (Walkthrough)

API 라우터 레이어에서 관리자 성격의 스캔 및 카테고리 CUD API들을 `api/admin.py` 모듈로 완벽히 격리·분리하여 소스 코드의 응집도를 높이고 단일 책임 원칙(SRP)을 강화했습니다.

## 변경 사항 요약 (Changes)

### API 라우트 레이어

#### [NEW] [admin.py](file:///c:/project/media_server/api/admin.py)
- [`api/library.py`](file:///c:/project/media_server/api/library.py)에 있던 다음 7가지 관리 및 스케줄러 관련 API 엔드포인트를 신규 Blueprint `media_admin`으로 이전하였습니다:
  1. `/api/media/libraries/add` (라이브러리 생성 및 백그라운드 즉시 스캔)
  2. `/api/media/libraries/edit` (라이브러리 수정 및 재스캔)
  3. `/api/media/libraries/delete` (라이브러리 및 하위 책 연쇄 소거)
  4. `/api/media/books/<int:book_id>/scan` (개별 도서 표지 단독 갱신 스캔)
  5. `/api/media/libraries/schedules` (카테고리별 크론 주기 상태 조회)
  6. `/api/media/libraries/<int:library_id>/scan` (지정 라이브러리 비동기 즉시 스캔)
  7. `/api/media/libraries/<int:library_id>/schedule` (크론 스케줄 등록/변경)

#### [MODIFY] [library.py](file:///c:/project/media_server/api/library.py)
- 이관 완료된 7가지 관리 API 구문을 삭제하여 순수 보관함 조회(목록, 상세, 히스토리 등) 역할만 남기도록 다이어트하였습니다.
- 더 이상 사용하지 않는 외부 모듈(`sqlite3` 등) 임포트를 정리했습니다.

#### [MODIFY] [__init__.py](file:///c:/project/media_server/api/__init__.py)
- 통합 Blueprint `api_bp`에 `admin_bp`를 임포트하여 하위 등록 완료하였습니다.

## 검증 결과 (Verification Results)
- 로컬 컴파일 점검(`py_compile`) 결과, 모듈 및 패키지 구조상 구문 오류가 전혀 없음을 확인했습니다.
- `deploy.py`를 실행하여 원격지 배포 및 Gunicorn 데몬 무중단 재구동을 에러 없이 성공적으로 수행 완료했습니다.
