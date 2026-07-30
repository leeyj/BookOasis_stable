---
title: "한글 구글 드라이브 UI(공유됨/압축 아카이브) 파싱 및 gdrive: 경로 무결성 조치"
category: "bugfix"
date: 2026-07-25
severity: "high"
affected_files:
  - "utils/drive_helper.py"
  - "tools/scanner/tasks.py"
tags: [gdrive_korean_ui_trimming, gdrive_canonical_path_fix, bugfix]
---

# 🐛 버그 수정 내역: 한글 구글 드라이브 UI('공유됨' 부가 문구) 파싱 및 gdrive: 가상 경로 무결성 조치

## 1. 현상 및 원인 분석
- 로그상 `01권#199.zip` 1개만 인지되고 나머지 `02권#191.zip` ~ `15권 完#193.zip` 및 `kavita.yaml` 파일이 스킵된 원인:
  - 한글 언어 환경 구글 드라이브 DOM `aria-label` 속성에 `'02권#191.zip Compressed archive 공유됨'` 과 같이 한글 부가 문구가 포함되어 파일명이 `공유됨`으로 오인되어 하위 폴더 404 재귀 호출이 발생함.
- `gdrive:/...` 가상 경로에 대해 `tasks.py`의 `os.path.getmtime` 호출 경고 예외 발생.

---

## 2. 조치 내용

1. **정규식 기반 확장자 정확 잘라내기 ([utils/drive_helper.py](file:///c:/project/media_server/utils/drive_helper.py))**:
   - `re.search(r'^(.*?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml|json))', raw_name)` 정규식을 도입하여 '공유됨', 'Shared', '압축 아카이브' 등 언어별 부가 문구와 상관없이 정확한 파일명 정제.
   - `'공유됨'`, `'Shared'` 문자열을 하위 폴더 재귀 목록에서 차단.

2. **가상 경로 I/O 스킵 예외 보완 ([tools/scanner/tasks.py](file:///c:/project/media_server/tools/scanner/tasks.py))**:
   - `if is_remote or root.startswith(('gdrive:', 'gdrive://')):` 예외 처리로 로컬 파일 스탯 호출 경고 완전히 제거.

---

## 3. 검증 결과

- Python 구문 검사(`python -m py_compile`) 통과.
- `python deploy.py`를 실행하여 원격 홈 서버 배포 및 서비스 정상 재기동 완료. 16개 도서 및 메타데이터 전량이 404 에러 없이 깔끔히 수집됨.
