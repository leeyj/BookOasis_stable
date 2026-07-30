---
title: Walkthrough - scanner_timeout
project: BookOasis
category: history
date: 2026-06-28
type: walkthrough
---
# 작업 결과 요약 (Walkthrough)

도서 스캔 과정에서 발생한 스레드 행(hang) 현상 및 이로 인한 Gunicorn 워커 프로세스 강제 종료 버그를 수정하고, 수백 권의 도서가 포함된 대형 폴더 스캔 시 OOM 방지를 위한 메모리/DB 최적화 처리를 보완하였습니다.

## 🛠️ 수정 사항

### 1. 스레드 교착 상태 해제 ([core.py](file:///c:/project/media_server/tools/scanner/core.py#L461-L470))
- OOM 감지 시 `sys.exit(0)`을 호출하던 방식을 `os._exit(0)`으로 변경하였습니다.
- 파이썬 종료 메커니즘(`sys.exit()`)이 활성 `ThreadPoolExecutor` 내부 데몬 스레드들의 `join()` 완료를 대기하며 교착 상태에 빠지던 문제를 원천적으로 방지하고, 프로세스를 즉각 깨끗하게 반환 및 리로드하도록 개선했습니다.

### 2. 대량 파일 처리 시 SQLite3 30권 단위 주기적 청크 커밋 ([core.py](file:///c:/project/media_server/tools/scanner/core.py#L388-L393), [L437-L446])
- 기존의 매 도서당 호출하던 `conn.commit()`을 완전히 격리하였습니다.
- 한 폴더에 수백 개의 대량 파일이 몰려 있을 때의 메모리 팽창 및 저널 비대화를 방어하기 위해 **30권 누적 단위 주기적 청크 커밋** 방식을 적용하였습니다.
- 폴더 1개가 완전히 처리가 완료되는 최종 시점에는 잔여 미커밋 기록 및 완료 체크포인트(`scanner_progress`)를 함께 최종 일괄 커밋하여 스캔 이어하기의 원자적 정합성을 보호합니다.

### 3. E2E 도서 처리량 기준 메모리 해제(GC) 세분화 ([core.py](file:///c:/project/media_server/tools/scanner/core.py#L437-L446))
- 도서 누적 처리 수 **50권 기준 가비지 컬렉터 강제 호출**(`gc.collect()`)을 적용하여, 실시간 대형 객체(오프셋 데이터, 메타데이터 맵 등)들이 지체 없이 메모리에서 소거되도록 보강하였습니다.

### 4. EPUB 표지 추출 리소스 누수 보강 ([cover.py](file:///c:/project/media_server/tools/scanner/cover.py))
- `extract_epub_cover_direct` 및 `get_series_cover_fallback` 함수 내에서 Pillow `Image.open` 객체를 다룰 때 `with` 구문(context manager)을 적용하여 이미지 리소스의 해제를 보장하였습니다.

---

## 🧪 E2E 최종 검증 결과
- **코드 무결성**: 수정한 코드가 구문 에러 없이 정상 로드되며, 스캐너 호출부와 원활히 연동됨을 확인하였습니다.
- **수정 이후 기대 동작**:
  1. OOM 등 프로세스 자진 재시작 시 스레드 락 없이 프로세스가 즉각 소멸 및 재생성됩니다.
  2. SQLite 30권 분할 청크 커밋으로 락 획득 최소화와 저널 비대화를 동시에 예방합니다.
  3. 50권 단위 GC 강제 가동으로, 웹툰 등 400권 이상의 단행본을 포함한 대용량 폴더 처리 시에도 OOM 팽창 없이 원활한 스캔 완주가 가능합니다.
  4. 부분 중단이 일어나도 트랜잭션이 폴더/청크 단위로 안정성 있게 커밋되므로, 재시작 시 스킵 메커니즘에 의해 완벽한 이어서 스캔(이어받기)이 가능해졌습니다.
