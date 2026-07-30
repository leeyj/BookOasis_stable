---
title: Walkthrough - init_docs
project: media_server
category: history
date: 2026-06-19
tags: [deploy, security, walkthrough]
type: walkthrough
---
# 배포 툴 점검 및 보안 강화 결과 보고

원격 서버 배포 경로 구성 점검 및 배포 도구 기능 강화를 완료하였습니다.

## 🛠️ 변경 사항 요약

- **`deploy.py` 배포 스크립트 수정**: 
  - `IGNORE_FILES` 목록을 추가하여 `.env`, `.env.example`, `deploy.py` 파일이 원격 서버에 중복 업로드되거나 덮어씌워지지 않도록 보안 필터링을 강화했습니다.
- **`.env.example` 추가**:
  - 독립 배포 및 협업을 지원하기 위한 환경 변수 템플릿 파일을 추가했습니다.

## 🧪 검증 결과

- 로컬 환경 변수 주입 테스트를 통해 배포 스크립트(`deploy.py`)를 안전하게 구동하였습니다.
- 업로드 과정에서 `.env`, `.env.example`, `deploy.py`가 성공적으로 제외되었음을 확인하였습니다.
- 원격 서버(192.168.0.20)의 5930 포트로 Gunicorn이 무중단 재구동되어 미디어 서버 데몬이 성공적으로 재부팅되었습니다.

---
*최종 배포 성공 (PID: 2456132)*
