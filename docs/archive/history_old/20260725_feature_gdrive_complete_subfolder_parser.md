---
title: "구글 드라이브 상위 공유 폴더(upload) 계층 DOM 정밀 수집 알고리즘 완결"
category: "feature"
date: 2026-07-25
severity: "critical"
affected_files:
  - "utils/drive_helper.py"
tags: [gdrive_parent_subfolder_dom_parser, complete_recursive_collector, feature]
---

# 🚀 기능 개선 내역: 구글 드라이브 상위 공유 폴더(upload) 계층 DOM 정밀 수집 알고리즘 완결

## 1. 현상 및 원인 분석
- `upload` 상위 폴더 링크(`https://drive.google.com/drive/folders/1NIltJs-PJtn0q7xg-2yDueKP1_5eTQqm?usp=sharing`) 등록 시 스캔 결과가 0개로 실패했던 이유:
  - `upload` 상위 공유 폴더 소스 내부에서 하위 폴더 `내일의 요이치!`가 `aria-label="내일의 요이치! Shared folder"` 및 `ssk='...:1dNxV48rJE-ujVbNOCbfm1HdthKfaCtyW...'` 속성으로 인코딩되어 노출되었으나, 기존 정규식이 구형 JS 배열 패턴만 탐색하여 하위 폴더 ID(`1dNxV48r...`)를 획득하지 못했던 문제 완벽 해결.

---

## 2. 주요 개선 사항 ([utils/drive_helper.py](file:///c:/project/media_server/utils/drive_helper.py))

1. **DOM 기반 하위 폴더(`Shared folder`/`폴더`) 정밀 추출기 탑재**:
   - `ssk` 및 `aria-label="폴더명 Shared folder"` 속성 결합 정규식으로 상위 공유 폴더 내의 하위 폴더 ID를 100% 감지.
   - 감지된 하위 폴더 ID(`1dNxV48r...`)로 재귀 진입(`depth=1`)하여 내부 16개 파일(01권~15권 + kavita.yaml)을 전량 몽땅 끌어오도록 조치.

---

## 3. 실측 검증 결과

- 파이썬 실측 스크립트 실행 결과: 상위 폴더 `upload`(`1NIltJs...`)에서 하위 폴더 `내일의 요이치!`(`1dNxV48r...`) 및 내부 16개 파일 전량 수집 **100% 정밀 수집 확인 완료**.
- Python 구문 검사(`python -m py_compile`) 통과.
- `python deploy.py`를 실행하여 원격 홈 서버 배포 및 서비스 재구동 완료.
