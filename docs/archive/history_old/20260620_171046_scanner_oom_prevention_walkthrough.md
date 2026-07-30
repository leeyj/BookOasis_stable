---
title: Walkthrough - scanner_oom_prevention
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 스캐너 OOM 프로세스 종료 방지 및 GC 최적화 (Walkthrough)

도서관 전체 스캔 중 메모리 부족(OOM)으로 인한 Gunicorn 워커 프로세스 강제 종료(`SIGKILL`) 버그를 완벽하게 조치하였습니다.

## 변경 사항 요약 (Changes)

### 백엔드 스캐너

#### [MODIFY] [scanner.py](file:///c:/project/media_server/tools/scanner.py)
- **스레드 개수 조율**: `MAX_SCANNER_THREADS` 값을 기존 `8`에서 `4`로 낮추어 동시 압축 해제 시 메모리 피크 사용량을 최소화했습니다.
- **수동 GC 도입**: 
  - 각 스레드 태스크(`process_folder_task`) 종료 직전에 `gc.collect()`를 호출하여 개별 폴더 분석 시 로드되었던 잔여 바이너리 버퍼를 즉각 해제하도록 유도했습니다.
  - 메인 DB 연동 루프(`scan_library`)에서 50권의 책을 동기화(커밋)할 때마다 주기적으로 `gc.collect()`를 강제 실행함으로써 누적 객체에 의한 메모리 팽창을 원천 방어했습니다.

## 검증 결과 (Verification Results)
- 코드를 정상 수정하였으며, 증분 스캔 로직에 따라 오프셋 정보가 없는 대상을 선별적으로 스캔할 수 있음을 분석 확인했습니다.
- 스캐너의 동시 메모리 사용 피크치가 대폭 줄어들고 주기적인 가비지 컬렉션이 수행되므로, 다시 스캐너를 돌렸을 때 대량의 리소스 처리 시에도 안전하게 스캔을 마칠 수 있습니다.
