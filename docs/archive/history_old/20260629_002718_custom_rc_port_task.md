---
title: Task - custom_rc_port
project: BookOasis
category: history
date: 2026-06-29
type: task
---
# 작업 계획 (Task)

- [x] DB 레이어 확장 (`database.py`)
  - [x] `libraries` 테이블 스키마에 `rclone_rc_url` 컬럼 추가
- [x] 백엔드 API & 비즈니스 로직 수정
  - [x] `services/category_service.py` (`add_library`, `edit_library`, `get_libraries`) 확장
  - [x] `api/admin.py` (`add_media_library`, `edit_media_library`, `update_library_schedule`) API 전송 데이터 매핑
  - [x] `tools/scanner/vfs.py` 캐시 새로고침 시 개별 라이브러리 고유 RC 주소 반영
- [x] 프론트엔드 UI/UX 컴포넌트 수정
  - [x] `templates/components/modals/library_modal.html`에 RC 주소 입력창 폼 그룹 마크업 추가
  - [x] `static/js/category.js` 모달 토글 인터랙션 바인딩, 데이터 적재 및 API 연동
  - [x] `templates/components/views/library_settings.html` 스케줄 설정 테이블 헤더에 Rclone RC 주소 열 추가
  - [x] `static/js/scheduler.js` 스케줄 설정 테이블 내 Rclone RC 주소 인풋 렌더링 및 저장 로직 구현
- [x] E2E 동작 검증 및 아카이빙
  - [x] 최종 화면 배포 후 기동 테스트 및 모달 토글, 개별 주소 스캔 작동 확인
  - [x] walkthrough.md 및 task.md 갱신 후 collect_docs.py 실행
