---
title: "카테고리 대량 삭제 전역 작업 차단 모달 및 뷰어 삭제 404 감지 안전 퇴장 방어막 적용"
category: "feature"
date: 2026-07-23
affected_files:
  - "static/js/modal.js"
  - "static/js/category.js"
  - "static/js/settings_trash.js"
  - "static/js/viewer/webtoon_viewer.js"
  - "static/js/viewer/comic_viewer.js"
tags: [delete, modal, overlay, viewer, 404, fallback, multi-device]
---

# 🚀 기능 및 방어막: 삭제 작업 차단 모달 & 뷰어 404 삭제 감지 안전 퇴장 처리

## 1. 개요 및 배경
- **배경 1 (대량 삭제 작업 차단)**: 5만 권 등 대량 도서가 포함된 카테고리 삭제나 휴지통 비우기 시 몇 초간 작업 시간이 소요될 때, 사용자가 중복으로 삭제 버튼을 누르거나 스캔 명령을 내리는 중복 입력을 차단해야 함.
- **배경 2 (멀티 디바이스 열람 중 삭제)**: 태블릿 등에서 만화/소설을 열어둔 상태에서 PC로 해당 카테고리를 지웠을 때, 태블릿 뷰어가 무한 로딩으로 먹통 되지 않고 삭제 사실을 알려주고 안전하게 퇴장해야 함.

## 2. 주요 구현 내용
1. **전역 작업 차단 로딩 모달 (`static/js/modal.js`)**:
   - `showGlobalLoadingSpinner(message)` & `hideGlobalLoadingSpinner()` 헬퍼 구현.
   - 반투명 딤 처리 오버레이와 애니메이션 스피너로 화면 입력을 100% 차단.
2. **삭제 실행 연동 (`static/js/category.js`, `static/js/settings_trash.js`)**:
   - `triggerDeleteLibrary` 및 `emptyTrashAll` 등 삭제 API 호출 시작 시 작업 차단 모달 구동 ➔ 삭제 완료/에러 시 해제.
3. **뷰어 404 삭제 감지 안전 퇴장 팝업 (`static/js/viewer/`)**:
   - 뷰어 이미지 스트리밍 / 오프셋 / 진척도 요청 중 `HTTP 404` 감지 시 "해당 도서(카테고리)가 서버에서 삭제되었습니다." 팝업 표출 후 메인 화면으로 안전 릴레이.

## 3. 검증 결과
- 프론트엔드 모듈 검증 및 멀티 디바이스 예외 상황에서의 안전 퇴장 처리 확인.
