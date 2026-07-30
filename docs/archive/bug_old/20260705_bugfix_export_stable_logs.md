---
title: "[버그수정] 배포본 소스 추출 시 개발자 로컬 로그 유출 결함 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-05
tags: [deploy, export, logs, gitignore, bugfix]
---

# 🐛 배포본 소스 추출 시 개발자 로컬 로그 유출 결함 조치

배포 버전 배포 스크립트(`export_stable.py`)를 통해 릴리즈 패키지를 만들 때 개발자 로컬 로그 디렉토리(`logs/`)가 필터링되지 않고 함께 동봉되어 배포되는 문제를 발견하여 조치 완료했습니다.

---

## 1. 버그 내역 및 현상
* **문제 상황**: 배포 버전을 설치한 일반 커뮤니티 사용자의 뷰어 및 스캔 에러 로그 파일에 개발자의 로컬 절대 경로(`/home/az001a/google/GDRIVE/...`)가 찍히는 현상 발생.
* **원인**: 
  - [export_stable.py](file:///C:/project/media_server/export_stable.py) 내 `EXCLUDE_DIRS` 상수 리스트에 `logs` 디렉토리가 누락되어 있어, 로컬 테스트 중 남은 `lazy_scanner.log` 등 실 데이터가 포함된 로그 디렉토리가 그대로 복사되어 최종 배포 버전에 삽입됨.
  - [.gitignore](file:///C:/project/media_server/.gitignore)에도 `logs/` 디렉토리가 미지정되어 로컬의 무관한 로그 파일들이 트래킹될 리스크를 동반함.

---

## 2. 해결 방안 및 수정 사항
1. **`export_stable.py` 제외 목록 추가**:
   - `EXCLUDE_DIRS` 집합에 `'logs'`를 포함하여 복사 빌드 탐색 과정에서 로그 폴더가 아예 누락되도록 제외 처리했습니다.
   - 단, 배포본의 구조 유지를 위해 빈 `logs/` 디렉토리는 복사 종료 후 `logs/.gitkeep`을 만드는 동적 생성 로직으로 처리하도록 `empty_dir` 목록에 `'logs'`를 추가 보강하였습니다.
2. **`.gitignore` 설정 보강**:
   - [.gitignore](file:///C:/project/media_server/.gitignore) 파일 최하단에 `logs/*` 및 `!logs/.gitkeep` 필터를 적용하여 개발 중 무심코 로그 내역이 Git 버전에 트래킹되는 상황을 방지했습니다.

---

## 3. 영향도 및 결과
* 향후 배포 스크립트를 재구동하여도 개발환경 로그(`/home/az001a/...` 등)가 외부 배포본으로 누출되지 않으며, 사용자 로컬 설치본은 항상 완전 무결한 빈 `logs/` 구조로 정상 시작됩니다.
