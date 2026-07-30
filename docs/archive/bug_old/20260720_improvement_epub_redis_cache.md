---
id: "20260720_improvement_epub_redis_cache"
date: 2026-07-20
category: "improvement"
severity: "medium"
status: "fixed"
tags: [redis, cache, epub, parse, performance]
---

# 20260720 — EPUB 파싱 데이터 Redis 캐싱 개선 완료

## 개선 목적

### 현상 및 병목
- EPUB 도서는 내부가 ZIP 압축 파일이며 XHTML 형식의 여러 챕터 파일로 쪼개져 있습니다.
- 책을 열거나 읽을 때마다 매번 ZIP 압축을 해제하고 HTML 구조 파싱, 불필요한 마크업 정제, 이미지 상대 경로를 API 서빙 주소로 치환하는 연산을 실시간 반복 수행해야 하므로 CPU 자원 낭비가 큽니다.

## 영향도
- 복잡한 EPUB 파싱 연산 결과(JSON 딕셔너리 구조)를 Redis 캐시에 12시간 동안 보존합니다.
- 다음 챕터 조회 및 도서 재진입 속도가 획기적으로 향상(레이턴시 0ms 수렴)되고, 서버 CPU 사용량이 감소합니다.

## 변경 사항

### 수정 파일 목록

#### `services/text_epub_content_service.py`
- `get_epub_content` 메서드 시작 시 Redis 캐시 키(`cache:epub:content:book:{book_id}`)를 검증하여 존재 시 json 역직렬화를 통해 즉각 반환.
- EPUB 파싱 완료 후 반환 결과 객체를 JSON 문자열로 직렬화하여 Redis 캐시에 12시간 만료(TTL 43200)로 저장.

## 해결 사항
- EPUB 데이터에도 Redis 고속 캐싱 아키텍처를 성공적으로 적용하여 뷰어 성능 최적화를 한 층 강화하였습니다.
