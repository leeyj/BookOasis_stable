---
title: "구글 드라이브 최신 DOM aria-label 및 ssk 속성 기반 정밀 파서 전면 탑재"
category: "feature"
date: 2026-07-25
severity: "high"
affected_files:
  - "utils/drive_helper.py"
tags: [gdrive_dom_aria_label_parser, ssk_attribute_extractor, feature]
---

# 🚀 기능 개선 내역: 구글 드라이브 최신 DOM aria-label 및 ssk 속성 정밀 파서 전면 탑재

## 1. 개요 및 원인 분석
- 사용자가 제공한 공유 URL(`https://drive.google.com/drive/folders/1dNxV48rJE-ujVbNOCbfm1HdthKfaCtyW?usp=sharing`)의 HTML 원문을 파이썬 스크립트로 직접 분석한 결과, 구글 드라이브 최신 Web App DOM에는 파일 정보가 단순 JS 배열이 아니라 **`aria-label="01권#199.zip Compressed archive Shared"`** 및 **`ssk='...:15_x5r48uJ76gTLacTFJJg3946R1DI_gC...'`** 속성 형태로 들어있음을 정밀 규명함.

---

## 2. 주요 개선 사항 ([utils/drive_helper.py](file:///c:/project/media_server/utils/drive_helper.py))

1. **`aria-label` + `ssk` DOM 정밀 파서 엔진 탑재**:
   - `ssk` 속성에서 25자리 구글 드라이브 고유 파일 ID 추출.
   - `aria-label` 속성에서 `01권#199.zip`, `kavita.yaml` 등의 정밀 파일명 추출 및 부가 설명 제거.

2. **백업 aria-label 파서 도입**:
   - 1차 매칭 실패 시 `aria-label` 단독 파싱 패턴으로 16개 파일(15개 만화 책 zip + 1개 kavita.yaml) 100% 검증 수집.

---

## 3. 실측 검증 결과

- 로컬 Python 분석 테스트 결과: `01권#199.zip` ~ `15권 完#193.zip` 및 `kavita.yaml` **총 16개 파일 100% 인지 확인 완료**.
- Python 구문 검사(`python -m py_compile`) 통과.
- `python deploy.py`를 실행하여 원격 홈 서버 배포 및 서비스 정상 재기동 완료.
