---
title: "스캔 중 파일 유실 방지를 위한 삭제 관리(휴지통) 기능 개발"
date: "2026-07-06"
type: "improvement"
status: "completed"
tags: ["scanner", "database", "trash", "frontend"]
---

# 스캔 중 파일 유실 방지를 위한 삭제 관리(휴지통) 기능 개발

## 1. 개요 및 배경
- Rclone VFS 마운트 환경에서 일시적인 네트워크 끊김이나 마운트 풀림 현상이 일어났을 때, 스캐너 엔진이 물리 파일 부재를 감지하고 DB 도서 정보와 개인 독서 진척도를 즉시 완전 삭제(Hard Delete)해버리는 문제를 인지했습니다.
- 이를 예방하기 위해 도서가 물리적으로 사라졌을 때 즉시 지우지 않고 `is_deleted = 1` 상태로 유보(Soft Delete)하며, 다음 스캔 시 파일이 재발견되면 자동으로 정상 원복(Auto-Recover)하는 방식을 도입했습니다.
- 최종 삭제 처리는 사용자가 명시적으로 확인하고 비울 수 있는 **[환경설정 -> 삭제 관리]** 탭을 제공하여 수동 승인 후 수행하도록 개선하였습니다.

## 2. 영향도
- **시스템 안정성 극대화**: 마운트 불안정이나 경로 오타 등 외부적 요인에 의해 사용자의 소중한 독서 진척도 및 별점 데이터 등이 강제로 소실될 가능성이 완전히 차단됩니다.
- **조회 성능 영향 최소화**: 도서 조회가 발생하는 핵심 Python 서비스 레이어(`series_service.py`, `book_detail_service.py`, `opds_service.py` 등)의 SQL 쿼리에 `COALESCE(is_deleted, 0) = 0` 조건을 인덱싱 친화적으로 바인딩하여 쿼리 오버헤드를 극소화했습니다.

## 3. 수정 및 신설 사항

### DB 스키마 수정
- [database.py](file:///c:/project/media_server/database.py): `books` 테이블 스키마에 `is_deleted INTEGER DEFAULT 0` 및 `deleted_at DATETIME DEFAULT NULL` 컬럼 추가.

### 스캐너 및 동기화 로직 수정
- [tools/scanner/sync_detector.py](file:///c:/project/media_server/tools/scanner/sync_detector.py): `handle_deleted_books()`를 개편하여 물리 삭제를 `UPDATE books SET is_deleted=1, deleted_at=CURRENT_TIMESTAMP`로 리팩토링하고, 물리적으로 재감지된 파일의 경우 `is_deleted=0, deleted_at=NULL`로 일괄 자동 복구하는 알고리즘 통합.

### 조회 서비스 레이어 Soft Delete 필터 추가
- [services/series_service.py](file:///c:/project/media_server/services/series_service.py)
- [services/book_detail_service.py](file:///c:/project/media_server/services/book_detail_service.py)
- [services/book_service.py](file:///c:/project/media_server/services/book_service.py)
- [services/opds_service.py](file:///c:/project/media_server/services/opds_service.py)
- [services/reading_history_service.py](file:///c:/project/media_server/services/reading_history_service.py)
  - 일반 도서 및 시리즈 목록 조회, 최근 추가된 항목, 최근 읽은 항목, 타치요미/미혼 OPDS API 등 핵심 SQL 구문에 `COALESCE(b.is_deleted, 0) = 0` 필터 주입 완료.

### 백엔드 제어 서비스 및 라우트 신설
- [services/trash_service.py](file:///c:/project/media_server/services/trash_service.py) [NEW]: 휴지통 목록 조회(`get_deleted_books`), 복구(`restore_books`), 영구 삭제(`empty_trash`) 비즈니스 서비스 설계. 영구 삭제 시 로컬 디렉토리 내 정적 커버 이미지 파일(`os.remove`)도 즉시 동반 삭제하도록 구현.
- [api/routes/trash_routes.py](file:///c:/project/media_server/api/routes/trash_routes.py) [NEW]: `/api/admin/trash`, `/api/admin/trash/restore`, `/api/admin/trash/empty` REST API 신설.
- [api/admin.py](file:///c:/project/media_server/api/admin.py): 신설 `trash_bp` 블루프린트 임포트 및 통합 관리자 Blueprint에 바인딩.

### 프론트엔드 UI 연동
- [templates/components/settings/trash_tab.html](file:///c:/project/media_server/templates/components/settings/trash_tab.html) [NEW]: 휴지통 관리용 정교한 HTML 그리드 템플릿 설계.
- [templates/components/views/library_settings.html](file:///c:/project/media_server/templates/components/views/library_settings.html): 설정 모달 탭 메뉴에 "삭제 관리" 탭 아이콘 및 버튼, include 템플릿 추가.
- [static/js/settings_trash.js](file:///c:/project/media_server/static/js/settings_trash.js) [NEW]: 삭제 대기 도서 로딩, 개별/선택 복구, 개별/선택 영구 삭제, 전체 휴지통 비우기 AJAX 통신 구현 및 `window.switchSettingsTab` 인터셉트 래핑.
- [static/js/settings_tab.js](file:///c:/project/media_server/static/js/settings_tab.js): 어드민 전용 탭(`adminOnlyTabs`) 리스트에 `trash` 추가 및 탭 전환 트리거 매핑.

## 4. 해결 확인사항 (E2E 검증 절차)
- DB 상에 `is_deleted = 1` 도서 세팅 시 일반 홈 대시보드와 OPDS 피드에서 보이지 않음을 검증.
- `삭제 관리` 탭 내에서 일반/성인 DB 도서 조회가 정확히 분류되어 출력되는지 확인.
- `복구` 시 즉시 복구 완료 얼럿과 함께 도서 대시보드에 책이 다시 렌더링되는 복원 성공 확인.
- `영구 삭제` 시 독서 기록을 포함한 도서 레코드가 DB에서 완벽하게 하드 딜리트되며, 동시에 로컬 디스크 내 실존하는 물리 커버 이미지도 깨끗하게 즉시 소거됨을 확인.
