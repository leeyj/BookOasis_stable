---
title: "알라딘 OpenAPI 상품 검색 최대 결과 수 상향 조정"
project: "BookOasis"
category: "improvement"
date: 2026-06-21
tags: [improvement, python, plugin, metadata, aladin]
---

# 🎨 알라딘 OpenAPI 상품 검색 최대 결과 수 상향 조정

## 1. 개선 내역 및 요청 사항
- **요청 사항**: 장편 도서(20권 초과 분량 등)를 수동 매칭하여 적용하고자 할 때 검색 결과 제한(기존 10개)으로 인해 뒤쪽 권수 선택 및 적용이 불가능한 현상 개선.
- **조치 사항**: 알라딘 OpenAPI ItemSearch API의 `MaxResults` 인자를 50개(API 스펙상 허용 최대치)로 대폭 상향하여 결과 노출 범위를 넓힘.

## 2. 영향도
- **영향 범위**: 알라딘 도서 메타데이터 수동 매칭 모달 검색 결과 목록
- **우선순위**: 보통 (기능 제약 해소)

## 3. 변경 상세 내용
- **수정 소스 파일**: `plugins/metadata/aladin.py`
- **조치 내용**:
  `search` 함수 내 `params` 딕셔너리에 매핑되는 API 파라미터 `MaxResults` 값을 기존 `10`에서 `50`으로 수정하였습니다.
  ```python
  params = {
      'ttbkey': ttbkey,
      'Query': query,
      'QueryType': 'Title',
      'MaxResults': 50,             # 반환할 최대 결과 수 (10에서 50으로 상향)
      'start': 1,
      'SearchTarget': 'Book',
      'output': 'js',
      'Version': '20131101'
  }
  ```

## 4. 해결 사항 및 검증 결과
- 수정 후 `deploy.py`를 통해 원격 배포 및 재구동을 진행하였고, 사용자가 직접 E2E 기능/레이아웃 검증을 수행하기로 확인하였습니다.
