---
title: "스캔 큐 대행 함수 실행 시 initial_add_scan 인자 불일치로 인한 TypeError 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, queue, argument-mismatch, python, typeerror]
---

# 🐛 스캔 큐 대행 함수 실행 시 initial_add_scan 인자 불일치로 인한 TypeError 조치

## 1. 버그 및 성능 이슈 내역
- **현상:** 백그라운드 스캐너 프로세스 기동 중 큐 대기열에서 특정 작업(예: 신규 카테고리 추가에 의한 스캔 등)을 처리하려 할 때 `Task processing crashed: _process_library_scan() got an unexpected keyword argument 'initial_add_scan'` 에러가 발생하며 스캔이 실패함.
- **원인:**
  1. 기존 `services/scanner_queue.py` 내의 `_process_library_scan` 및 `_process_cover_scan`은 고정 키워드 인자(`db_type, db_path, library_id, physical_path, force=False`)를 받도록 설계됨.
  2. 도서 스캔을 생성하는 컨트롤러 레이어에서 `initial_add_scan` 등의 부차적인 제어 파라미터를 추가로 주입하여 큐에 인큐함.
  3. 자식 워커 루프가 이 작업을 언패킹(`**kwargs`)하여 `_process_library_scan`으로 넘길 때 선언되지 않은 파라미터가 유입되어 파이썬 `TypeError` 예외가 발생함.

## 2. 영향도
- **큐 장애:** 신규 도서 추가 시 자동 트리거되는 백그라운드 스캔 태스크가 즉각 크래시되어 기동되지 않고 큐가 먹통이 됨.

## 3. 수정 사항 (수정 소스 파일 목록)
- **[services/scanner_queue.py](file:///c:/project/media_server/services/scanner_queue.py)**
  - `_process_library_scan` 및 `_process_cover_scan` 함수의 인자 시그니처를 `**kwargs` 가변 인자 형식으로 래핑함.
  - 큐로부터 들어오는 모든 딕셔너리 파라미터를 그대로 포워딩(`run_scan_job(**kwargs)`)하도록 고쳐, 파라미터가 유동적으로 변하더라도 에러 없이 100% 호환되도록 교정.

## 4. 해결 사항 및 E2E 검증 결과
- **인자 불일치 원천 해소:** 가변 인자 포워딩 처리에 의해 `initial_add_scan`을 포함한 임의의 제어용 인자들이 에러 없이 전달되어 작업이 정상 수행됨.
- **안정적 인큐 및 디스패치:** 수정 코드 배포 후 `initial_add_scan`이 들어간 라이브러리 스캔 작업도 정상 처리됨을 E2E 검증 완료.
