---
title: "비활성화된 메타데이터 플러그인 노출 오류 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, metadata, plugin, search]
---

# 비활성화된 메타데이터 플러그인 노출 오류 수정

## 1. 버그 내역 및 증상
- 환경설정 > 플러그인에서 특정 메타데이터 검색 플러그인(예: '알라딘 오늘의 신간 데스크' 등)을 비활성화했음에도 불구하고, 개별 도서 우클릭 메뉴의 '알라딘 메타데이터 검색' 수동 검색창 드롭다운 목록에 해당 플러그인이 여전히 활성화된 것처럼 노출되는 현상.

## 2. 원인 분석
- `/api/media/metadata/plugins` API 진입 시 호출되는 `MetadataService.get_searchable_plugins()`에서 플러그인 활성 상태 필드(`enabled` 속성)를 체크하지 않고 데이터베이스에 등록된 모든 검색 가능 플러그인을 그대로 프론트엔드로 전달하고 있었음.

## 3. 조치 사항
- **메타데이터 플러그인 노출 필터링 교정 (`services/metadata_service.py`)**:
  - `get_searchable_plugins` 정적 메소드 내에서 `MetadataFactory.get_all_searchable_providers()` 결과의 개별 플러그인 아이템에 대해 `enabled` 속성이 `True`인 항목만 리스트 컴프리헨션을 통해 걸러내도록 수정함 (`p.get('enabled', True)`).
  - 이에 따라 사용자가 환경설정에서 비활성화한 메타데이터 검색 플러그인은 수동 메타데이터 검색창 목록에서 즉각 제외됨.

## 4. 해결 확인 및 영향도
- 수정 후 특정 메타데이터 플러그인을 비활성화한 다음 수동 메타데이터 검색 모달을 실행한 결과, 비활성화한 플러그인이 드롭다운 목록에서 깔끔하게 사라지는 것을 검증 완료함.
