---
title: Walkthrough - null_series_crash_fix
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 워크쓰루: 스캔 에러 리포트 저장 및 환경설정 리포트 뷰어 구현

스캔 중 발생하는 파일 손상(BadZipFile) 및 표지 추출 실패 등의 오류 정보를 수집하여 `cache/reports` 아래 JSON 형식으로 저장하고, 환경설정 내 리포트 뷰어 전용 탭에서 확인할 수 있도록 구현 완료하였습니다. 또한 카테고리 삭제 시 관련 리포트 파일들이 함께 영구 삭제되도록 처리했습니다.

## 변경 내용

### 1. 백엔드 에러 수집 및 순환 삭제 유틸 구현
- **[NEW] [report_helper.py](file:///c:/project/media_server/utils/report_helper.py)**: 스캔 오류 정보를 수집해 `{library_id}_{timestamp}.json` 파일로 저장하고, 라이브러리별 최신 10개의 리포트만 유지하며 구형 파일을 순환 소거(링 버퍼)하는 로직을 구현하였습니다. `delete_all_reports`를 구현하여 카테고리 삭제 시 리포트 파일을 연쇄적으로 물리 삭제하도록 하였습니다.

### 2. 스캐너 오류 감지 및 연동
- **[MODIFY] [core.py](file:///c:/project/media_server/tools/scanner/core.py)**: 폴더별 I/O 스캔 작업(`process_folder_task`) 내부에서 `BadZipFile`, `ValueError` (표지 누락), 기타 예외를 개별 파일 단위로 포착하여 수집하고, `scan_library` 완료 시 리포트 저장을 수행하도록 동기화하였습니다.

### 3. 카테고리 삭제 연계 처리
- **[MODIFY] [category_service.py](file:///c:/project/media_server/services/category_service.py)**: `delete_library` 실행 시 DB 삭제에 앞서 `delete_all_reports`를 실행하여 고아 파일이 남지 않도록 완결성을 다졌습니다.

### 4. 리포트 조회 및 상세 조회 API 구현
- **[MODIFY] [admin.py](file:///c:/project/media_server/api/admin.py)**:
  - `GET /api/media/libraries/<library_id>/reports`: 특정 카테고리의 리포트 목록을 최신순으로 정렬하여 조회하는 API.
  - `GET /api/media/libraries/reports/view`: 파일 경로 탈취 방지 처리가 적용된 리포트 상세 데이터 조회 API.

### 5. 프론트엔드 UI 마크업 및 테이블 연동
- **[MODIFY] [tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**: 환경설정 탭에 '스캔 리포트' 단추를 추가하고, 리포트별 오류 내역(도서 파일명, 오류 구분, 상세 사유 및 경로)을 테이블로 표시하는 뷰어 영역을 추가하였습니다.
- **[MODIFY] [settings_tab.js](file:///c:/project/media_server/static/js/settings_tab.js)**: 탭 전환 핸들러 연동 및 라이브러리 목록, 리포트 목록, 특정 리포트 에러 내역을 비동기로 렌더링하는 함수(`initReportsTab`, `loadReportList`, `loadReportDetail`)를 추가 구현하였습니다.
- **[MODIFY] [api.js](file:///c:/project/media_server/static/js/api.js)** & **[MODIFY] [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)**: API 호출 헬퍼 추가 및 글로벌 윈도우 바인딩을 적용하였습니다.
- **[MODIFY] [modal.js](file:///c:/project/media_server/static/js/modal.js)**: 상세 정보 뷰 하단의 "추천 매칭" 및 "메타정보 검색" 버튼이 부모 플렉스 컨테이너(`flex-direction: column`) 영향으로 수직 적재되던 현상을 해결하기 위해 가로 플렉스 컨테이너(`display: flex; gap: 0.5rem;`)로 감싸 두 버튼이 가로로 나란히 표시되도록 레이아웃을 최적화하였습니다.

## 검증 결과
- `python -m py_compile` 구문 분석을 통해 로컬 컴파일 성공을 확인하였습니다.
- `python deploy.py`를 실행하여 원격 홈 서버(`192.168.0.20`)로 변경된 백엔드, 프론트엔드 자산을 안정적으로 배포하고, 미디어 서버 데몬 프로세스를 정상 재구동 완료하였습니다.
