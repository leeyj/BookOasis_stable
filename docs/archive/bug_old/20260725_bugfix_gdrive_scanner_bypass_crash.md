---
title: "구글 드라이브 원격 웹 링크 카테고리 스캔 시 rclone VFS 캐시 새로고침 헛수고/경고 우회 처리"
category: "bugfix"
date: 2026-07-25
severity: "medium"
affected_files:
  - "tools/scanner/vfs.py"
  - "services/scheduler_service.py"
  - "utils/drive_helper.py"
tags: [gdrive_url, rclone_vfs_bypass, scheduler_service, scanner_vfs, bugfix]
---

# 🐛 버그 수정 내역: 구글 드라이브 원격 웹 링크 스캔 시 rclone VFS 새로고침 우회 조치

## 1. 현상 및 원인 분석

- **현상**:
  - 구글 드라이브 공유 웹 링크 카테고리 스캔 시, 로그에 `VFS 갱신 후보 경로 시도... non-success response - file does not exist` 경고가 연달아 출력되며 약 5초간 지연 후 스캔이 완료됨.

- **원인**:
  - `services/scheduler_service.py`와 `tools/scanner/vfs.py`에서 `is_remote_path(path)`가 `True`일 때, 무조건 rclone VFS REST API(`vfs/refresh`)를 호출하려고 시도함.
  - 하지만 구글 드라이브 웹 공유 링크(`https://drive.google.com/drive/folders/...`)는 rclone VFS 로컬 마운트 디렉토리가 아닌 웹 URL이므로 rclone API에서 당연히 `file does not exist`로 응답함.

---

## 2. 조치 내용

1. **rclone VFS 새로고침 대상에서 구글 드라이브 웹 URL 전면 제외 ([tools/scanner/vfs.py](file:///c:/project/media_server/tools/scanner/vfs.py))**:
   - `trigger_vfs_refresh` 내 `remote_paths` 추출 시 `not is_gdrive_url(p)` 필터 조건을 추가하여 rclone RC API 호출을 완전 우회.

2. **스케줄러/트리거 레이어 분기 ([services/scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py))**:
   - `has_remote_paths` 판별 시 `is_remote_path(p) and not is_gdrive_url(p)`로 수용하여 rclone VFS 강제 갱신 로직에 진입하지 않고 0.01초 만에 즉시 스캔 성공으로 넘어가도록 분기 처리.

---

## 3. 검증 결과

- Python 구문 검사(`python -m py_compile`) 통과.
- `python deploy.py`를 통해 원격 홈 서버에 배포 완료. 구글 드라이브 카테고리 스캔 시 rclone VFS 갱신 경고 및 지연 없이 즉시 완료됨.
