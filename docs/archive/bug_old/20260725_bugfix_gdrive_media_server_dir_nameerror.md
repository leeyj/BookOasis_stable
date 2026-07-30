---
title: "drive_helper.py 내 MEDIA_SERVER_DIR 정의 누락 NameError 조치"
category: "bugfix"
date: 2026-07-25
severity: "medium"
affected_files:
  - "utils/drive_helper.py"
tags: [media_server_dir_nameerror, drive_helper_bugfix, bugfix]
---

# 🐛 버그 수정 내역: drive_helper.py 상단 MEDIA_SERVER_DIR 누락 NameError 조치

## 1. 현상 및 원인
- `fetch_gdrive_folder_files`에서 `load_dotenv`를 호출할 때 사용된 `MEDIA_SERVER_DIR` 상수가 `utils/drive_helper.py` 상단에 미선언되어 `NameError: name 'MEDIA_SERVER_DIR' is not defined` 예외 발생.

---

## 2. 조치 내용

- `utils/drive_helper.py` 최상단에 `MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` 정의를 추가하여 NameError 완벽 조치.

---

## 3. 검증 결과

- Python 구문 검사(`python -m py_compile`) 통과.
- `python deploy.py`를 실행하여 서버 배포 완료. NameError 예외 없이 스캐너 파서가 정상 구동됨.
