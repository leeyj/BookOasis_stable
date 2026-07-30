---
title: "손상 DB 복구 및 db_recovery.py CLI 인수 지원 개선"
project: "BookOasis"
category: "bug"
date: 2026-07-19
tags: [db, recovery, cli]
---

# 🛠️ 손상 DB 복구 및 db_recovery.py CLI 인수 지원 개선

## 1. 장애 및 필요성 (Issue & Background)
- 사용자로부터 전달된 `test/chinh_media_general.db` (549MB) 파일에 대해 손상 의심 신고가 접수됨.
- 기존의 `tools/db_recovery.py` 스크립트는 `media_general.db`, `media_adult.db` 두 개의 고정된 파일만 한꺼번에 복구하도록 하드코딩되어 있어 임의의 테스트용 DB 파일이나 특정 DB를 개별적으로 복구하기 어려웠음.
- 또한 대화형 실행(`yes` 입력 대기)으로 인해 자동화 파이프라인이나 스크립트 기반 동작 시 중단이 발생하는 제약이 존재함.

## 2. 조치 사항 (Resolution Details)
- **`tools/db_recovery.py`** 소스 코드를 다음과 같이 개선:
  - `argparse` 모듈을 연동하여 `--db` 인자를 제공받도록 개선. 인자 지정 시 해당 특정 경로의 단일 DB 파일만 복구 모드로 동작하게 리팩토링함.
  - `--yes` 옵션을 제공하여 확인 프롬프트(confirm) 입력을 생략하고 즉시 수행될 수 있도록 처리하여 비대화식 무인 실행을 지원함.
  - 경로를 지정하지 않을 경우 기존처럼 기본 DB(일반/성인용)를 일괄 처리하게 하여 하위 호환성을 완벽 유지함.
- **`chinh_media_general.db` 복구 수행**:
  - `python tools/db_recovery.py --db test/chinh_media_general.db --yes` 실행.
  - STEP 1 단계인 WAL 체크포인트와 sqlite 무결성 사전 체크(`integrity_check`)를 정상 통과(`ok`).
  - 추가로 STEP 3 FTS5 검색 인덱스 재빌드 작업을 정상 완수.
  - 최종 검증 결과 `✅ OK` 판정을 확인하여 DB 손상이 해소되거나 정상임을 확인함.

## 3. 관련 소스 파일 (Affected Files)
- [db_recovery.py](file:///c:/project/media_server/tools/db_recovery.py)
