---
title: "Kavita 마이그레이션 시 저자, 출판사, 발행일, 줄거리, 장르, 태그 정보 이관 고도화"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, migrator, database, metadata, migration]
---

# 🧠 [Bugfix] Kavita 마이그레이션 시 저자, 출판사, 발행일, 줄거리, 장르, 태그 정보 이관 고도화 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: `tools/migrator.py`를 실행하여 1번 메뉴(Kavita ➡️ BookOasis 이관)를 수행할 때
- **장애 현상**: 카비타에서 수집해 둔 도서의 핵심 메타정보인 저자(Person), 출판사(Publisher), 발행일(ReleaseDate), 줄거리(Summary), 장르(Genre), 태그(Tag)가 정상 연동 이관되지 않고 생략되거나 기본값으로 하드코딩 저장되는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 이관 직후 사용자가 북오아시스 사이트 내에서 작가 이름으로 검색하거나, 장르 및 태그 기반 필터링 기능을 정상적으로 활용할 수 없어 카비타로부터의 이관 체감이 심히 반감되는 문제를 유발했습니다.

---

## 3. 원인 파악 (Root Cause)
- Kavita는 관계형 스키마(N:M 관계 테이블)로 저자, 장르, 태그 등을 쪼개서 관리하지만, 북오아시스는 단일 컬럼에 쉼표(`,`) 구분자를 둔 문자열 데이터로 단순 저장하는 형태의 데이터 구조 차이 때문입니다.
- 기존 이관 스크립트는 이 브릿지 테이블들을 조회해 그룹 취합하는 구문이 누락되어 있어 임의 기본값(`Kavita Author`, `Kavita Publisher`) 및 Null 값으로 일괄 강제 시딩하고 있었습니다.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [migrator.py](file:///c:/project/media_server/tools/migrator.py#L115-L131,L191-L225)
- 카비타 SQLite DB 추출용 메인 쿼리에 `PersonSeriesMetadata`, `GenreSeriesMetadata`, `SeriesMetadataTag` 등의 관계 브릿지 테이블들을 연결하여, 저자(Role=1인 작가), 장르, 태그 텍스트 배열을 쉼표 `, ` 구분자로 그룹 병합하는 **`GROUP_CONCAT` 서브쿼리들**을 동적 빌드 추가했습니다.
- 아울러 출판사, 발매 연월일(ISO date parsing 처리), 줄거리 텍스트도 매핑하여 `books` 테이블의 해당 컬럼들에 하드코딩 없이 안전하게 동적 바인딩하여 삽입되도록 튜닝 완료하였습니다.

---

## 5. 최종 검증 (Verification)
- `media_general.db`를 깨끗이 비운 후 `python tools/migrator.py`를 가동하여 1번 모드로 전체 데이터 이관을 새로이 집행하였습니다.
- 이관 직후 `media_general.db` 내 `books` 테이블을 검증 조회한 결과, 저자(예: `전혜진`), 장르(예: `SF, 아포칼립스`), 태그 정보 및 줄거리가 쉼표 구분자 형태로 정규화되어 풍부하게 채워지고 필터링이 즉각 실시간 동작하는 것을 최종 확인하였습니다.
