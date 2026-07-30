---
title: "단일 PDF 즉시 스캔 격리 실행 및 락 충돌 방지 구현"
project: "BookOasis"
category: "feature"
date: 2026-06-22
tags: [pdf, single-scan, subprocess, fitz, lock]
---

# 단일 PDF 즉시 스캔 격리 실행 및 락 충돌 방지 구현

## 1. 개선 내역
- 우클릭을 통해 단일 도서 또는 시리즈의 PDF 도서 재스캔을 요청할 때 발생할 수 있는 fitz 라이브러리의 OOM(메모리 초과)이나 세그멘테이션 폴트(Segfault) 등의 오류로부터 Flask 웹 서버 프로세스의 안전성을 확보하기 위해, 스캔 작업을 **독립 백그라운드 프로세스**(`lazy_scanner.py --book-id {book_id}`)로 격리하여 비동기 실행하도록 개선했습니다.
- 전역 백그라운드 스캐너가 이미 작동 중일 때(`lazy_scanner.lock` 파일 존재 시) 중복 서브프로세스 기동으로 인한 SQLite DB 락 충돌(`database is locked`)을 차단하기 위해, 자동으로 처리를 대기 및 순차 처리로 위임하는 예외 처리를 연동했습니다.

## 2. 영향도
- **영향 범위**: 단일 도서 재스캔 서비스 ([services/book_scan_service.py](file:///c:/project/media_server/services/book_scan_service.py)), Lazy 표지 스캐너 ([tools/lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py))
- **개선 효과**: PDF 파일 표지 추출 시에도 Flask 프로세스의 크래시 위험이 제거되어 시스템 안정성이 비약적으로 상향되었으며, 락 경합 시 동시 구동을 예방해 DB 무결성을 유지합니다.

## 3. 수정 사항
- **[tools/lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py)**:
  - `--book-id <book_id>` 명령줄 아규먼트를 파싱하여 단일 도서 스캔 모드를 지원합니다.
  - 단일 스캔 기동 시 전역 스캔 락 파일이 존재하면 즉시 세션을 스킵하고, 그렇지 않은 경우 개별 락(`lazy_single_{book_id}.lock`)을 취득해 실행합니다.
  - 단일 스캔 모드에서는 순연 딜레이(`time.sleep(3.0)`)를 무시하고 타겟 도서의 표지만을 즉각 렌더링하고 DB를 갱신하도록 수정했습니다.
- **[services/book_scan_service.py](file:///c:/project/media_server/services/book_scan_service.py)**:
  - 즉시 스캔 대상 포맷이 PDF인 경우를 사전에 식별합니다.
  - `lazy_scanner.lock` 전역 락 감지 시, 새로운 subprocess를 띄우지 않고 대기 위임 성공 메시지를 응답합니다.
  - 락이 없을 때만 `subprocess.Popen`을 활용해 독립된 서브프로세스로 안전하게 비동기 즉시 스캔 처리를 위임 실행합니다.

## 4. 해결 사항
- 이제 웹 서버에 부하를 주지 않고 단일 PDF 도서의 즉시 표지 복원 요청을 격리되어 안전하게 백그라운드 기동할 수 있습니다.
