---
title: "카테고리 저장 시 원격 VFS os.walk 지연 및 alert 블로킹 개선"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [category, performance, vfs, os_walk, show_toast, improvement]
---

# 🚀 [개선 및 버그 수정] 카테고리 저장 시 원격 VFS os.walk 지연 및 alert 블로킹 개선

## 1. 개요 및 원인
- **현상**: 카테고리 설정 모달에서 '저장' 버튼 클릭 시 모달이 닫히지 않고 '처리 중...' 상태로 몇 초~십 수 초간 오랫동안 멈춰 서 있는 현상 발생.
- **원인 분석**:
  1. **백엔드 네트워크 I/O 병목**: 구글 드라이브나 rclone VFS 마운트 경로(`/home/az001a/google/GDRIVE/...`) 카테고리 저장 시 `detect_library_media_mismatch`가 `os.walk`를 실행하면서 클라우드 디렉터리를 훑어 서버 HTTP 응답이 극심하게 지연되었음.
  2. **프론트엔드 자바스크립트 블로킹**: 응답 수신 후 `alert(result.message)` 팝업창이 떠 있는 동안 브라우저 이벤트 루프가 멈춰 `closeLibraryModal()`이 실행되지 못하고 뒤편의 버튼이 '처리 중...' 상태로 동결되었음.

## 2. 주요 조치 사항 (수정 파일)

### 1) [`c:\project\media_server\api\helpers\validation.py`](file:///c:/project/media_server/api/helpers/validation.py) & [`api\routes\library_routes.py`](file:///c:/project/media_server/api/routes/library_routes.py)
- `detect_library_media_mismatch` 호출 시 `is_remote` 파라미터 및 `is_remote_path(path)` 원격 경로 감지 시 `os.walk` 탐색을 **즉시 스킵(Skip)** 하도록 조치 (서버 응답 속도 < 100ms 확보).

### 2) [`c:\project\media_server\static\js\category\crud_controller.js`](file:///c:/project/media_server/static/js/category/crud_controller.js)
- 저장 성공 시 `closeLibraryModal()`을 최우선 실행하여 모달 UI를 즉시 닫고 `showToast`로 안내하도록 개편.

## 3. 해결 결과
- 사용자 승인 후 홈 서버 배포(`python deploy.py`) 완료 (Server PID: 765476 / Worker PID: 765535).
- 카테고리 저장 시 지연 없이 모달이 즉시 닫히고 토스트 알림과 함께 카테고리가 쾌적하게 저장됨을 확인 완료.
