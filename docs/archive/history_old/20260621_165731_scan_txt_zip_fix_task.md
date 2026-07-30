---
title: Task - scan_txt_zip_fix
project: BookOasis
category: history
date: 2026-06-21
type: task
---
# 작업 목록 (TODO List)

- [x] `tools/scanner/cover.py` 내의 표지 자동 추출 시 확장자 조건 분기 고정
  - [x] `.zip`, `.cbz` 확장자만 `zipfile.ZipFile` 분석을 거치도록 명시적 제한
- [x] 서버 배포 및 변경사항 원격 반영 (`deploy.py` 실행)
- [x] 버그 수정 이력 문서 작성 (`docs/bug` 폴더 내에 YYYYMMDD_bugfix 문서 작성)
- [x] E2E 교차 검증 및 기능 테스트 (텍스트 파일 스캔 오류 제외 확인)
