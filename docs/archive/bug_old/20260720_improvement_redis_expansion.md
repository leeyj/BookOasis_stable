---
id: "20260720_improvement_redis_expansion"
date: 2026-07-20
category: "improvement"
severity: "medium"
status: "fixed"
tags: [redis, cache, performance, txt, stream, stage]
---

# 20260720 — Redis 적용 범위 확장 (1단계: 뷰어 캐싱, 2단계: 스캔 상태 캐싱) 완료

## 개선 목적

### 현상 및 병목
1. **스트리밍 캐시 프로세스 간 비공유**: Gunicorn 멀티 프로세스 환경에서 로컬 메모리 RAM 캐시(`SizedLRUCache`)가 서로 공유되지 않아 Gunicorn 워커 프로세스 간에 중복 연산 발생 및 RAM 사용량 비효율화 발생.
2. **소설(TXT) 인코딩 변환 비용**: 인코딩 변환 처리(UTF-8, CP949, EUC-KR 등)를 거치는 텍스트 소설 로딩 작업은 매번 디바이스 I/O 및 CPU 리소스를 소모함.
3. **스캔 중 무거운 SQLite 쓰기 부하**: 스캔의 진행 상황이나 세부 상태(`stage`)를 갱신할 때마다 자잘하게 일어나는 SQLite `UPDATE` 부하 완화 및 Redis 기반 캐싱 데이터 구조 필요.

## 영향도
- 이미지 스트리밍 캐시가 전역 Redis로 확장되어 다중 워커 환경 및 재기동 후에도 캐시 히트율이 안정적으로 보장됨.
- 텍스트 파일 서빙 레이턴시가 크게 단축됨.
- 스캔 진척도 정보를 SQLite 대신 Redis에서도 즉각 읽어갈 수 있는 고속 조회 경로 인프라 확보.

## 변경 사항

### 수정 파일 목록

#### `services/stream_page_service.py` (1단계)
- `extract_page` 시작 시 Redis 캐시(`cache:stream:book:{book_id}:page:{page_idx}`)를 조회해 존재하면 base64 디코딩 후 반환하는 고속 경로 추가.
- 추출 성공 시 bytes 데이터를 base64로 안전하게 인코딩하여 Redis에 1시간 만료(TTL 3600)로 세팅.

#### `services/text_epub_content_service.py` (1단계)
- `get_txt_content` 시작 시 Redis 캐시(`cache:txt:file:{path_hash}`)를 검사해 있으면 즉시 리턴.
- 파일 디코딩 결과를 Redis에 12시간 동안 보관하여 중복 CP949/UTF-8 인코딩 변환 비용을 최소화.

#### `services/scheduler_service.py` (2단계)
- `_update_task_stage` 실행 시, SQLite DB 갱신과 동시에 Redis 키 `status:scan:stage:{task_key}`에 상태(VFS refresh, book_scan 등)를 캐싱 처리.

## 해결 사항
- Redis를 고속 뷰어 캐시(1단계) 및 진행률(2단계) 캐싱 시스템으로 본격적으로 동원하여 성능 최적화를 완성.
