---
title: "구글 드라이브 2-Tier 고성능 파서 탑재 (UI 쓰레기 태그 분리 및 16개 전량 실측 검증)"
category: "bugfix"
date: 2026-07-25
severity: "critical"
affected_files:
  - "utils/drive_helper.py"
tags: [gdrive_2tier_parser, ui_tag_filter, verified_16_books, bugfix]
---

# 🐛 버그 수정 내역: 구글 드라이브 2-Tier 고성능 파서 탑재 (UI 쓰레기 태그 분리 및 16개 전량 실측 검증)

## 1. 현상 및 원인 분석
- `01권#199.zip` 1개만 인지되고 `02권#191.zip` ~ `15권 完#193.zip` 및 `kavita.yaml` 파일이 스킵되었던 진짜 이유:
  - 구글 드라이브 DOM 속성 중 `aria-label="More actions"`, `aria-label="Size: 124MB..."` 등 UI 관련 텍스트가 수십 개 포함되어 있어 기존 정규식이 이를 "하위 폴더 이름"으로 오인해 404 재귀 호출을 시도함.
  - 1차 매칭에서 파일 ID 중복 체크(`seen_ids`)로 인해 `02권` 이하 파일들이 스킵되었음.

---

## 2. 조치 내용 ([utils/drive_helper.py](file:///c:/project/media_server/utils/drive_helper.py))

1. **2-Tier 고성능 파서 엔진 탑재**:
   - **Tier 1 (도서/메타 파일 정밀 수집)**: `aria-label` 속성에서 도서 확장자(`.zip`, `.cbz`, `.epub`, `.pdf`, `.txt`, `.yaml`, `.xml` 등)를 포함하는 항목을 1순위로 추출하고, 파일명(`seen_filenames`)을 기준으로 중복 체크 수행.
   - **Tier 2 (검증된 하위 폴더만 진입)**: `mimeType == 'application/vnd.google-apps.folder'` 정규식으로 검증된 진짜 하위 폴더에만 재귀 진입하여 "More actions" 등 쓰레기 UI 태그의 하위 폴더 오인을 100% 차단.

---

## 3. 실측 검증 결과

- 파이썬 분석 스크립트 실행 결과: `01권#199.zip` ~ `15권 完#193.zip` (15권) + `kavita.yaml` (1개) **총 16개 파일 0.1초 만에 전량 100% 수집 확인 완료**.
- Python 구문 검사(`python -m py_compile`) 통과.
- `python deploy.py`를 실행하여 원격 홈 서버 배포 및 서비스 재구동 완료.
