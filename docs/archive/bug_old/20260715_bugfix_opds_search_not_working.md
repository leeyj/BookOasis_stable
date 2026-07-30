---
id: bugfix-20260715-opds-search-not-working
date: 2026-07-15
type: bugfix
severity: high
status: fixed
affected_files:
  - api/opds_common/xml.py
  - api/opds.py
tags: [opds, search, koreader, chunky, opensearch]
---

# 버그 리포트: OPDS 검색 버튼 미동작 (KOReader, Chunky 등)

## 버그 내용
KOReader, Chunky Reader, Panels 등 외부 OPDS 앱에서 검색을 눌러도 결과가 나오지 않는 문제.

## 원인 분석
build_opds_xml의 검색 링크가 OpenSearch Description 문서만 가리키는 형태로,
application/atom+xml 타입의 직접 검색 URL 템플릿이 없었음.

## 수정 사항
- api/opds_common/xml.py: 직접 검색 URL 템플릿 링크 추가 (type=application/atom+xml)
- api/opds.py: OpenSearch Description에 opds-catalog 프로파일 Url 추가
