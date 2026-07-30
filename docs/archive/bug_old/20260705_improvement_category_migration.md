---
title: 카테고리 데이터 마이그레이션(이동) 기능 추가
date: 2026-07-05
author: leeyj (Carls)
type: improvement
---

# 카테고리 데이터 마이그레이션(이동) 기능 추가

## 1. 개선 배경 및 필요성
* **사상적 배경**: 미성년자에게 성인도서가 노출되는 사고를 원천 차단하기 위해, BookOasis는 설계 시점부터 일반도서(`media_general.db`)와 성인도서(`media_adult.db`)의 데이터베이스 파일을 물리적으로 완벽히 격리해 관리하고 있습니다.
* **사용자 피드백 요구사항**: 잘못된 보관함에 카테고리를 등록하고 스캔했거나, 분류를 일반에서 성인으로 또는 성인에서 일반으로 변경하고자 할 때 카테고리를 삭제하고 다시 스캔할 필요 없이 바로 이동시킬 수 있는 기능이 필요하다는 피드백이 수수되었습니다.
* **해결해야 하는 병목**: 단순히 SQL `UPDATE` 쿼리 한 줄로 해결되지 않으며, 서로 다른 두 개의 SQLite 파일 간에 카테고리, 도서, 오프셋(`book_offsets`), 읽기 로그(`user_reading_log`), 진척도(`user_progress`) 등 연관 테이블 데이터들을 관계형 무결성에 손상 없이 복제 이관하는 트랜잭션 마이그레이션 파이프라인이 수반되어야 합니다.

## 2. 세부 구현 및 수정 사항
### 백엔드 (Python API 및 서비스)
* **[services/category_service.py](file:///c:/project/media_server/services/category_service.py)**:
  - `move_library(from_type, to_type, library_id)` 메서드를 추가했습니다.
  - 소스 DB와 목적지 DB의 2개 커넥션을 획득하여 단일 트랜잭션 하에서 이관을 시도하고 실패 시 롤백합니다.
  - 이관 도중 `books` 의 ID가 목적지에서 새롭게 생성되므로, 구 도서 ID와 신규 도서 ID의 매핑 관계(`book_id_map`)를 메모리에서 매핑 추적하여 `book_offsets`, `user_progress`, `user_reading_log` 등의 연관 외래키(foreign key)를 정상적으로 보존하고 매핑해 주었습니다.
  - 이관 완료 후 소스 DB의 잔여 도서 및 카테고리를 역순으로 삭제하고 비동기로 DB 최적화(`optimize_database`)를 실행합니다.
  - **[버그 수정]** 커넥션 풀 고갈 방지를 위해 `move_library()` 및 `check_duplicate_path_warnings()` 호출 성공/실패 여부와 관계없이 반드시 `finally` 블록에서 데이터베이스 커넥션을 풀에 반환(`conn.close()`)하도록 누수 결함을 완벽히 보완했습니다.
* **[api/routes/library_routes.py](file:///c:/project/media_server/api/routes/library_routes.py)**:
  - `/api/media/libraries/move` 포스트 엔드포인트를 신설하여 스케줄러에서 구 카테고리 작업을 삭제하고 이관을 수행한 뒤 스케줄러를 리로드합니다.

### 프론트엔드 (UI 및 연동)
* **[templates/components/modals/library_modal.html](file:///c:/project/media_server/templates/components/modals/library_modal.html)**:
  - 카테고리 수정 모달 푸터에 "이동" 버튼(`library-form-move-btn`)을 추가하여 수정 화면에서만 노출되도록 마크업을 변경했습니다.
* **[templates/components/tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**:
  - 대량 이관 작업 시 DB 쓰기 락 충돌 및 사용자 이중 조작(동시성 버그)을 원천 차단하기 위해, 전체 화면을 가리고 클릭 입력을 제한하는 흐림 로딩 오버레이 모달(`migration-dimmer-modal`)을 마크업에 신설했습니다.
* **[static/js/category.js](file:///c:/project/media_server/static/js/category.js)**:
  - `triggerAddLibrary()`와 `triggerEditLibrary()` 호출 시 이관 이동 버튼의 가시성(display) 및 라벨("성인도서로 이동" / "일반도서로 이동")을 유동적으로 변경해 줍니다.
  - `triggerMoveLibrary()` 비동기 함수를 추가하여 로딩 디머(Dimmer) 작동, `/api/media/libraries/move` API 통신, 이관 성공 후 목적지 보관함(일반 ↔ 성인)으로 자동 탭 스위칭 및 사이드바 새로고침 처리를 유기적으로 연동했습니다.

## 3. 해결 성과 및 의의
* **안정적인 아키텍처 수호**: 단일 DB 통합과 같은 보안 타협 없이도 기존의 물리 격리 보안 설계(Air Gap)를 100% 수호하며 데이터 이동 편의성을 완벽하게 제공합니다.
* **사용자 경험 극대화**: 이관이 진행되는 동안 화면 잠금 로딩창을 띄워 데이터 충돌 및 UI 오작동 가능성을 완벽하게 배제했습니다.
