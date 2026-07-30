---
title: "도서 스캔 중 쓰레드 행 및 Gunicorn 워커 타임아웃 오류 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-06-28
tags: [scanner, gunicorn, deadlock, sqlite, oom]
---

# 도서 스캔 중 쓰레드 행 및 Gunicorn 워커 타임아웃 오류 수정

## 1. 버그 내역

- 스캐너 비동기 동작 중 OOM 방지 임계치를 감지했을 때 `sys.exit(0)`을 호출하여 강제 종료를 처리하는 과정에서, `ThreadPoolExecutor` 내부 활성 워커 스레드들의 종료를 대기(`join()`)하다가 교착 상태(Deadlock)에 빠져 프로세스가 멈추는 현상 발생.
- 멈춘 프로세스로 인해 Gunicorn 마스터 프로세스의 하트비트 체크가 실패하여 Gunicorn이 워커에 SIGABRT 신호를 보내 강제 종료시킴 (`SystemExit: 1` 트레이스 발생).
- 도서 검사 진행 중 매 도서의 DB 인서트/업데이트마다 `conn.commit()`이 개별적으로 호출되어 SQLite 파일 독점 락(Exclusive Lock) 시간이 증가하고 경합이 과도해져 스캐너의 멈춤 현상을 극대화함.
- 폴더 하나에 수백 권의 책이 몰려 있는 경우(예: 웹툰 폴더 등), 단순 폴더 단위의 일괄 커밋 방식을 사용하면 단일 트랜잭션 내 데이터 적재가 과도하여 SQLite 저널 메모리 팽창으로 인한 OOM이 추가 발생할 위험이 발견됨.

## 2. 영향도

- **영향 범위**: 도서관 스캔(`scan_library`) 기능 전반 및 Gunicorn 웹 서비스
- **장애 현상**: 대량 스캔 중 무응답 상태에 빠져 웹 로그인이 풀리고, 프로세스가 비정상 강제 종료됨. 대형 폴더 스캔 시 저널 메모리 비대화 위협.

## 3. 수정 사항

### [1] OOM 감지 시 데드락 없는 즉시 종료 처리

**수정 소스 파일**: [`tools/scanner/core.py`](file:///c:/project/media_server/tools/scanner/core.py)

- OOM 임계값 감지 시 `sys.exit(0)` 호출 대신 `os._exit(0)`을 사용해 데몬 스레드들의 `join()` 대기 락에 걸리지 않고 즉시 해당 워커 프로세스를 완전히 반환하도록 교체. Gunicorn 마스터는 죽은 워커 프로세스 감지 즉시 깨끗한 상태의 워커 프로세스를 안전하게 리로드함.

### [2] SQLite3 트랜잭션 최적화 및 주기적 청크 커밋 도입

**수정 소스 파일**: [`tools/scanner/core.py`](file:///c:/project/media_server/tools/scanner/core.py)

- 파일 스캔 처리 루프 내 개별 도서당 매번 수행되던 `conn.commit()`을 제거.
- 대형 폴더 내 수백 개 파일 처리 시 OOM 및 저널 팽창을 방어하기 위해 **30권 단위 주기적 청크 커밋**(`conn.commit()`) 구조를 적용하여 트랜잭션을 합리적으로 분할하고 독점 락 점유 시간을 최소화함.
- 폴더가 완전히 종료되는 최종 시점에는 잔여 미커밋 기록 및 완료 체크포인트(`scanner_progress`)를 일괄 커밋하여 스캔 이어하기 기능을 보호함.

### [3] E2E 도서 처리량 기준 메모리 해제(GC) 세분화

**수정 소스 파일**: [`tools/scanner/core.py`](file:///c:/project/media_server/tools/scanner/core.py)

- 폴더 개수 기준 가비지 컬렉션(`gc.collect()`) 외에, 누적 처리된 도서 개수 기준 **50권 단위 강제 메모리 회수** 로직을 도입하여 실시간 메모리 누수를 추가 차단.

### [4] EPUB 커버 이미지 추출 리소스 누수 방지

**수정 소스 파일**: [`tools/scanner/cover.py`](file:///c:/project/media_server/tools/scanner/cover.py)

- `extract_epub_cover_direct` 및 `get_series_cover_fallback`에서 Pillow의 `Image.open` 객체가 블로킹되거나 반환 지연이 없도록 `with` 문(context manager)을 적용하여 이미지 객체가 정상 범위 내에서 강제로 닫히고(close) 리소스가 신속히 해제되도록 방어 코드 적용.

## 4. 해결 사항

- 스캐너의 빈번한 DB 쓰기 락 경합이 제거되어 대용량 폴더 스캔 속도와 안정성이 크게 향상됨.
- 프로세스 강제 리로드 시 스레드 교착 상태가 근본적으로 제거되어 Gunicorn이 임의로 비정상 `SystemExit: 1`을 터뜨리는 현상을 원천 방지함.
- 웹툰 등 수백 개의 단행본이 몰린 대형 폴더에서도 OOM 위협 없이 조밀하고 안전하게 분할 트랜잭션 저장을 수행할 수 있게 됨.
- 비정상 종료되더라도 폴더 완료 상태의 트랜잭션 정합성이 유지되어 스캐너 재기동 시 정상적으로 스캔 이어하기가 지원됨.
