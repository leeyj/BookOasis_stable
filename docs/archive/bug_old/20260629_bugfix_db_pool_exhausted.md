---
title: "스캔 중 미디어 조회 시 DB 커넥션 풀 고갈 버그 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, database, connection-pool]
---

# 🧠 [Bugfix] 스캔 중 미디어 조회 시 DB 커넥션 풀 고갈 오류 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 라이브러리 스캔 진행 중 메인 페이지 진입 혹은 조회 API 호출 시
- **장애 현상**: `Database connection pool exhausted. Timeout waiting for connection.` 에러와 함께 '최근 읽은 도서' 및 '신규 추가 도서' 조회에 실패하여 UI에 로딩 실패 메시지가 나타나는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 대용량 라이브러리 스캔 작업 시 수 분~수십 분간 사용자가 미디어 서버의 웹 UI를 원활하게 탐색하거나 만화책을 정상적으로 읽을 수 없어 심각한 사용성 저하를 유발함.

---

## 3. 원인 파악 (Root Cause)
- 기본 설정된 DB 커넥션 풀 크기(`DB_POOL_SIZE = 5`)가 스캐너의 동시 백그라운드 스레드 점유에 비해 지나치게 적었음.
- 백그라운드 스캔 도중 SQLite 커넥션이 모두 점유되어, 사용자의 프론트엔드 API 호출이 커넥션 확보를 위해 30초 동안 대기하다가 풀 고갈 타임아웃을 반환한 것이 원인임.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)
기본 풀 크기를 10개로 상향하고, 사용자가 필요시 늘릴 수 있는 최대 임계값 한도를 20개에서 30개로 확장함.

### [MODIFY] [database.py](file:///c:/project/media_server/database.py#L129-L134)
- `_get_pool_size_raw()` 내 최대 풀 크기 제한을 20에서 30으로 상향함.
- `default_settings`의 `DB_POOL_SIZE` 시딩 기본값을 `5`에서 `10`으로 상향함.

### [MODIFY] [library_settings.html](file:///c:/project/media_server/templates/components/views/library_settings.html#L112-L117)
- 커넥션 풀 설정 인풋 필드의 `max` 속성을 30으로, 기본 `value` 속성을 10으로 조정함. 
- 관련 설명 텍스트 레이블의 안내 한도를 최대 30개로 업데이트함.

### [MODIFY] [general.js](file:///c:/project/media_server/static/js/settings/general.js#L59-L60)
- DB_POOL_SIZE 바인딩 시 백업 기본값 문자열을 `'5'`에서 `'10'`으로 변경함.

---

## 5. 최종 검증 (Verification)
- 소스 코드 변경 적용 후 DB 커넥션 풀의 기본값 및 한계 범위가 정상 작동하며, 대용량 폴더 스캔 중에 웹 UI 접속을 병행 시도하여도 락 및 고갈 현상 없이 신속하게 미디어 데이터 조회가 정상적으로 수행됨을 확인함.
