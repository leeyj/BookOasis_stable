---
title: "독립 스캐너 스크립트 ImportError 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-04
tags: [scanner, import-error, cli, bugfix]
---

# 🐛 독립 스캐너 스크립트 ImportError 결함 조치 리포트

## 1. 장애 및 버그 내역
- **현상**: CLI 터미널 환경에서 스캐너 독립 기동 명령인 `python3 tools/scanner.py`를 실행했을 때, 아래의 임포트 에러를 발생시키며 즉시 종료되는 현상.
  ```text
  Traceback (most recent call last):
    File "/app/tools/scanner.py", line 10, in <module>
      from tools.scanner.core import (
  ImportError: cannot import name 'process_folder_task' from 'tools.scanner.core' (/app/tools/scanner/core.py)
  ```
- **원인**: `tools/scanner.py`에서 `tools.scanner.core` 모듈에 정의되지 않은 내부 태스크 처리 함수(`process_folder_task`), 포맷 튜플(`SUPPORTED_FORMATS`), 스레드 설정 상수(`MAX_SCANNER_THREADS`)를 잘못된 경로에서 임포트하려고 했던 구문 결함.

## 2. 영향도 (Impact Area)
- **웹 서비스 영향도 없음**: 웹 UI 환경에서의 수동 스캔 기동 및 크론 스케줄링 동기화 스캔은 `services` 모듈의 내부 큐를 사용해 핵심 스캔 코드를 다이렉트로 가져와 기동하므로, 본 결함에 영향을 받지 않고 완전히 정상 작동함.
- **CLI 도구 오작동**: 도커 컨테이너 외부/내부 터미널에서 `tools/scanner.py`를 단독 기동하여 동기화를 수동으로 집행하고자 했던 사용자들에게 스캐너 기동 불가 장애가 발생함.

## 3. 조치 사항 및 해결 내용
- **수정 소스 파일**: [tools/scanner.py](file:///c:/project/media_server/tools/scanner.py)
- **조치 내용**: 
  - `tools.scanner.core`에 존재하지 않는 개체들의 임포트 경로를 실제 정의된 물리적 위치에 맞춰 교정 및 분리하였습니다.
    - `process_folder_task`, `SUPPORTED_FORMATS` -> `tools.scanner.tasks` 모듈에서 로드하도록 교정
    - `MAX_SCANNER_THREADS` -> `tools.scanner.engine` 모듈에서 로드하도록 교정

---
*최종 작성일: 2026-07-04*
