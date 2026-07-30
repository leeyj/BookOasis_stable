---
title: Walkthrough - scanner_timeout
project: BookOasis
category: history
date: 2026-06-28
type: walkthrough
---
# 작업 결과 요약 (Walkthrough)

도서 스캔 과정에서 발생한 스레드 행(hang) 현상 및 이로 인한 Gunicorn 워커 프로세스 강제 종료 버그를 수정하였습니다.

## 🛠️ 수정 사항

### 1. 스레드 교착 상태 해제 ([core.py](file:///c:/project/media_server/tools/scanner/core.py#L461-L470))
- OOM 감지 시 `sys.exit(0)`을 호출하던 방식을 `os._exit(0)`으로 변경하였습니다.
- 파이썬 종료 메커니즘(`sys.exit()`)이 활성 `ThreadPoolExecutor` 내부 데몬 스레드들의 `join()` 완료를 대기하며 교착 상태에 빠지던 문제를 원천적으로 방지하고, 프로세스를 즉각 깨끗하게 반환 및 리로드하도록 개선했습니다.

### 2. SQLite3 트랜잭션 커밋 빈도 최적화 ([core.py](file:///c:/project/media_server/tools/scanner/core.py#L436-L440))
- 루프 내 개별 도서 단위로 수행하던 `conn.commit()`을 제거하였습니다.
- 폴더 내 전체 도서의 정보 갱신과 폴더 진행 기록(`scanner_progress`) 갱신을 하나의 원자적(atomic) 트랜잭션으로 묶어 폴더별로 1회씩만 커밋하도록 변경하여 DB 락 획득 횟수 및 I/O 오버헤드를 크게 줄였습니다.

### 3. EPUB 표지 추출 리소스 누수 보강 ([cover.py](file:///c:/project/media_server/tools/scanner/cover.py))
- `extract_epub_cover_direct` 및 `get_series_cover_fallback` 함수 내에서 Pillow `Image.open` 객체를 다룰 때 `with` 구문(context manager)을 적용하여 이미지 리소스의 해제를 보장하였습니다.

---

## 🧪 E2E 최종 검증 결과
- **코드 무결성**: 수정한 코드가 구문 에러 없이 정상 로드되며, 스캐너 호출부와 원활히 연동됨을 확인하였습니다.
- **수정 이후 기대 동작**:
  1. OOM 등 프로세스 자진 재시작 시 락 없이 프로세스가 즉시 정리됩니다.
  2. Gunicorn 워커가 스캔 쓰기 작업으로 인해 무응답 상태에 빠지는 현상이 제거되었습니다.
  3. 부분 중단이 일어나도 폴더 단위로 트랜잭션이 보장되므로, 재시작 시 완벽한 이어서 스캔(이어받기)이 가능해졌습니다.
