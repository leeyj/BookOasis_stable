---
title: "메타데이터 검색 및 전파 과정 내 상세 콘솔 디버그 로그 추가"
project: "BookOasis"
category: "bug"
date: 2026-06-29
tags: [metadata, debug, console_log, logging]
---

# 🧠 메타데이터 검색 및 전파 과정 내 상세 콘솔 디버그 로그 추가

## 1. 개선 내역
- **현상**: 시리즈 모드 메타데이터 적용 후 여전히 간헐적으로 상세 설명 및 표지가 꼬이거나 유실되는 현상이 재현되어, 사용자와 개발자 모두 브라우저 F12 콘솔에서 문제 상황을 실시간으로 추적·식별할 수 있도록 단계별 디버그 로그 주입이 요구됨.

## 2. 영향 범위
- 메타데이터 매칭 적용 비동기 흐름 제어 스크립트 (`static/js/metadata_search.js`)

## 3. 수정 사항
- **JS 스크립트 수정** (`static/js/metadata_search.js`):
  - `applyMetadata` 호출 직전, 완료 직후 (`[MetadataApply-DEBUG] 1단계 결과 ...`)
  - 시리즈 전파 분기 기동 상태 및 `fetchMediaDetail` 응답 결과
  - 도서 리스트 탐색 및 `targetBook` 일치 매칭 여부 보고 (`2.2단계 targetBook 탐색 완료: ...`)
  - `copyMetadata` 폼 데이터 조립 파라미터 내역 및 API 수신 결과
  - 최종 리렌더링 `window.openBookDetail` 실행 직전의 인자 전달 상태 (`3단계: openBookDetail 호출하여 화면 갱신 시도 ...`)
  - 각 처리 블록 에러 및 catch 분기점에 상세 `console.error` 추가

## 4. 해결 사항
- 브라우저 개발자 도구의 콘솔 창에서 1단계 단권 반영부터 2단계 시리즈 전파, 3단계 리렌더링까지 전체 라이프사이클의 입출력 데이터를 눈으로 추적 가능해짐.
