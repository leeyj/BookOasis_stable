---
title: Walkthrough - custom_rc_port
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# 작업 결과 요약 (Walkthrough)

카테고리별로 독립적인 Rclone RC API 주소를 입력 및 관리하고, 원격 드라이브 체크박스의 토글에 따라 UI 폼이 부드럽게 노출되도록 하는 연동 기능을 성공적으로 완료하였습니다.

## 🛠️ 수정 사항

### 1. DB 스키마 확장 및 마이그레이션 ([database.py](file:///c:/project/media_server/database.py#L228-L232))
- `libraries` 테이블 구조에 `rclone_rc_url` TEXT 컬럼을 새롭게 추가하여 개별 저장소를 마련했습니다.
- DB 초기화 구문에 반영되어 서버 기동 시 자동으로 `ALTER TABLE`이 수행되어 기존 DB에 컬럼이 마이그레이션됩니다.

### 2. 백엔드 비즈니스 로직 및 API 확장
- **비즈니스 로직 ([category_service.py](file:///c:/project/media_server/services/category_service.py#L6-L50))**: 라이브러리 추가, 수정, 조회 시 `rclone_rc_url` 값을 안전하게 맵핑하도록 SQL 쿼리와 함수 인자를 보완했습니다.
- **REST API ([admin.py](file:///c:/project/media_server/api/admin.py#L47-L52))**: 카테고리 추가 및 수정 API 엔드포인트에서 폼 데이터 파라미터 `rclone_rc_url`을 정상적으로 수집하도록 수정했습니다.
- **VFS 스캐너 개선 ([vfs.py](file:///c:/project/media_server/tools/scanner/vfs.py#L20-L42))**: 캐시 새로고침 시, 전역 설정보다 **현재 스캔 대상인 라이브러리의 개별 `rclone_rc_url` 컬럼 데이터**를 우선 탐색하여 개별 포트(5572, 5573 등)로 정밀 타격 갱신 신호를 보냅니다.

### 3. 프론트엔드 UI/UX 폼 동적 노출 및 데이터 바인딩
- **HTML ([library_modal.html](file:///c:/project/media_server/templates/components/modals/library_modal.html#L19-L23))**: "원격 드라이브 여부" 체크박스 아래에 `rclone_rc_url` 입력 필드 그룹 마크업을 동적으로 추가했습니다.
- **JS 인터랙션 ([category.js](file:///c:/project/media_server/static/js/category.js#L220-L245))**:
  - 카테고리 추가/수정 모달 기동 시 체크박스 상태(`is_remote`)에 맞춰 Rclone RC 주소 텍스트 박스를 스마트하게 열고(`display: block`) 닫습니다.
  - 저장 시 `FormData`에 담아 서버 API로 안전하게 전송합니다.

---

## 🧪 E2E 최종 검증 결과
- **정상 연동 확인**: 카테고리 수정창을 켰을 때 "원격 드라이브"에 체크하면 rclone RC API 주소를 입력하는 텍스트 박스가 나타나며, 저장 시 DB까지 값이 안전하게 이식되는 것을 검증했습니다.
- **동적 스캔 포트 지정**: 5573 등 다른 포트로 지정된 원격 드라이브에 대해 캐시 새로고침(`vfs/refresh`)이 성공적으로 해당 전용 포트를 타고 갱신 완료되는 흐름을 확인했습니다.
