---
title: Walkthrough - frontend_cover_pollution
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 모달 Fixed 정중앙 고정 버그 조치 결과

## 1. 개요 및 목적
- **이슈**: 페이지 하단으로 스크롤 후 알라딘 검색 모달을 띄웠을 때, 조상 컨테이너의 `transform` 영향으로 fixed 포지션이 오작동하여 화면 중앙을 이탈해 문서 위쪽에 모달이 처박히는 버그 해결.
- **해결 방안**: 돔 로드 완료 시점에 모든 모달(`.library-modal`) 돔 엘리먼트를 HTML body 바로 아래로 옮겨(Append) 조상 컨테이너의 레이아웃 간섭을 원천 배제함.

## 2. 작업 상세 내역
- **프론트엔드 엔트리 조율기 수정**: [static/js/tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
  - `DOMContentLoaded` 리스너 상단에 `.library-modal` 돔들을 순회하며 `document.body.appendChild` 처리를 수행하는 자동 돔 교정 로직 추가.

## 3. 검증 결과
- **로컬 검증 완료**: 자바스크립트 구문 이상 없음.
- **원격 검증 대기**: 배포 및 실물 기동 테스트는 사용자 확인 하에 원격지에서 직접 수행 예정.
