---
title: "성인전용 OPDS 카탈로그 피드 경로 규격화 및 접속 불능 결함 해결 (/opds-adult)"
category: "bugfix"
date: 2026-07-22
severity: "medium"
affected_files:
  - "api/opds.py"
  - "api/app_opds.py"
tags: [opds, opds-adult, route, fix]
---

# 성인전용 OPDS 카탈로그 피드 경로 규격화 및 접속 불능 결함 해결 (/opds-adult)

## 1. 결함 원인 분석
- 성인 OPDS 피드 최상위 주소인 `/opds-adult`는 이미 라우트 자체는 등록되어 있었으나, 내부 하위 하이퍼링크 `href`의 Prefix 주소가 `/opds/adult/library/<id>`, `/opds/adult/recently-added` 등 혼용되어 생성되면서 외부 뷰어 클라이언트(Moon+ Reader, KOReader, KyBook 등)가 하위 카테고리 진입 시 최상위 규격 `/opds-adult/...`와 엇갈려 피드를 불러오지 못하거나 404/인증 오류를 발생시키는 원인이 확인되었습니다.
- 또한 `<link rel="start">` 태그의 루트 주소가 성인 피드 요청 시에도 `/opds`로 고정 작성되어 뷰어 클라이언트가 상위로 이동할 때 일반 보관함으로 이탈하는 문제도 함께 발견되었습니다.

## 2. 주요 수정 사항
- **[api/opds.py](file:///c:/project/media_server/api/opds.py)**
  - `_opds_xml` 헬퍼 함수에서 `is_adult=True`일 때 `start_path`를 `/opds-adult`로 정확히 지정하도록 보완.
  - `opds_adult_root` 최상위 피드 렌더링 시 하위 링크 주소를 `/opds-adult/library/<id>`, `/opds-adult/recently-added`, `/opds-adult/recently-read`, `/opds-adult/favorite`로 일관되게 규격화.
  - 기존 구형 호환 링크(`/opds/adult/...`)와의 하위 호환성을 위해 `@opds_bp.route('/opds-adult/...')` 별칭 라우트를 함께 등록.
- **[api/app_opds.py](file:///c:/project/media_server/api/app_opds.py)**
  - 앱 전용 OPDS 피드(`app_opds.py`)에서도 `is_adult=True`일 때 `start_path`가 `/app-opds-adult`로 정확히 생성되도록 동기화.

## 3. 검증 결과
- 표준 OPDS 클라이언트에서 `/opds-adult` 주소 등록 및 인증(Basic Auth - admin 전용) 후 하위 라이브러리, 시리즈, 최신작 목록 피드 렌더링이 막힘 없이 원활하게 구동됨을 확인함.
