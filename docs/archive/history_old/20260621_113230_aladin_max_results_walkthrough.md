---
title: Walkthrough - aladin_max_results
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 워크쓰루: 알라딘 OpenAPI 상품 검색 최대 결과 수 상향 조정

장편 시리즈 도서 수동 매칭 시 모든 권수가 노출되지 않아 매칭할 수 없었던 제한을 해제하기 위해 OpenAPI 상품 검색 API 파라미터 `MaxResults` 값을 기존 `10`에서 `50`으로 상향 변경하였습니다.

## 변경 내용

### 1. API 검색 결과 노출 수 상향

#### [MODIFY] [aladin.py](file:///c:/project/media_server/plugins/metadata/aladin.py)
- `search` 함수 파라미터인 `MaxResults` 값을 `10`에서 `50`으로 변경하였습니다.

## 검증 결과

- 로컬 변경 내역 검증 후, 배포 스크립트 `python deploy.py`를 실행하여 원격 홈 서버(`192.168.0.20`) 배포를 완료하였습니다.
- 권수가 많은 장편 도서 검색을 시도하여 10개를 초과하는 권수들이 검색 결과에 모두 표시되고 매칭 적용이 원활하게 진행되는지 확인합니다.
