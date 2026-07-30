---
id: "20260720_bugfix_scanner_memory_guard"
date: 2026-07-20
category: "bugfix"
severity: "high"
status: "fixed"
tags: [scanner, memory, guard, oom, sigkill, sqlite, corruption]
---

# 20260720 — 스캐너 메모리 가드(OOM 방지) 이식 완료

## 버그 내역

### 현상
- 대용량 도서 표지 추출(Lazy-Scanner) 수행 시, 수천 권의 압축 ZIP/EPUB 해제 및 WebP 렌더링이 연속해서 수행됨에 따라 메모리 누수가 발생.
- 운영체제(OS)의 RAM 한계를 초과하여 스캐너 워커 프로세스(`lazy_scanner.py`)가 `SIGKILL(kill -9)`로 비정상 강제 즉사하는 장애 유발.
- 정리 코드가 돌지 못한 상태로 커넥션이 뜯겨나가, SQLite 쓰기 중이던 WAL 파일과 메인 DB의 정합성이 꼬이고 `database disk image is malformed` (DB 영구 손상) 현상이 유발됨.

### 근본 원인
- `lazy_scanner.py` 가 장시간 대량 스캔 중일 때 메모리를 점진적으로 많이 소비하며, 이를 능동적으로 억제하거나 자진 회피하는 가드 장치가 없었음.

## 영향도
- OOM 크래시로 인해 SQLite 데이터베이스 파일이 영구 파손되어 스캔 도구를 완전히 구동할 수 없는 임계 장애 발생.

## 수정 사항

### 수정 파일 목록

#### `tools/lazy_scanner.py`
- 루프 진입부(`for book, offset_only in folder_books:`)에 `psutil` 기반 메모리 가드 추가.
- 매 도서 한 권 처리 시점마다 자신의 RSS 메모리를 측정하고, 임계치(**550MB**) 초과 시 활성 SQLite DB 연결(`conn`)을 안전하게 정리(`close()`)한 뒤 `sys.exit(0)`을 호출하도록 조치.
- 종료코드 `0`으로 반환하므로 부모 큐 매니저(`scanner_queue.py`)에서는 작업을 성공(`completed`)으로 안정 마감 처리하고, 다음 크론 스케줄 기동 시 0MB 상태의 깨끗한 메모리에서 남은 스캔 작업을 이어 처리하도록 아키텍처 개선.

## 해결 사항
- 프로세스 강제 즉사(SIGKILL)를 사전에 차단하고 스스로 우아하게 자진 정상 종료하므로, OOM 및 SQLite 데이터베이스 영구 손상 리스크를 원천 해결하였습니다.
