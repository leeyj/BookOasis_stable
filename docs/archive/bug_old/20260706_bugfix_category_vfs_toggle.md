---
title: "카테고리 원격 드라이브(VFS) 토글 시 RC 주소 입력창 미노출 버그 수정"
project: "BookOasis"
category: "bug"
date: 2026-07-06
tags: [bugfix, category, vfs, rclone, front-end]
---

# 🐛 카테고리 원격 드라이브(VFS) 토글 UI 동기화 오류 조치 보고서

## 1. 버그 내역 (Bug Report)
- **현상**: 카테고리 추가 시, 경로 자동 감지 등으로 원격 드라이브(VFS) 체크박스(`library-form-remote`)가 true로 설정되더라도 Rclone RC API 주소 입력창 및 원격 드라이브 관련 경고 UI가 노출되지 않음.
- **원인**: JavaScript 코드 상에서 DOM 요소의 `checked` 프로퍼티 값을 직접 수정하는 방식으로 토글할 경우, 브라우저는 표준 `change` 이벤트를 강제로 트리거하지 않습니다. 따라서 `library-form-remote` 요소에 바인딩된 `change` 이벤트 리스너가 작동하지 않아 뷰가 동기화되지 않았던 것입니다.

## 2. 영향도 (Impact Assessment)
- **영향 범위**: 카테고리(라이브러리) CRUD 관리 팝업 UI
- **부작용**: 사용자가 VFS 기능이 켜져 있는 것처럼 보임에도 Rclone RC API 주소를 수정할 수 있는 인풋 필드가 표시되지 않아, 체크박스를 수동으로 한 번 해제했다가 다시 선택해야만 입력할 수 있어 사용자 경험에 지장을 유발함.

## 3. 수정 사항 및 해결 사항 (Resolutions)
- **수정 소스 파일**: [category.js](file:///c:/project/media_server/static/js/category.js)
- **상세 조치 사항**:
  1. `triggerAddLibrary()` 함수에서 폼을 초기화하고 VFS 체크박스를 기본값(`false`)으로 비활성화한 직후, `dispatchEvent(new Event('change'))`를 호출하여 UI의 표시 상태를 명시적으로 동기화하도록 처리함.
  2. `detectAndUpdateRemoteFlag(path)` 함수 내에서 경로 자동 감지로 `isRemoteCheckbox.checked` 값이 동적으로 변경될 때, 동일하게 `dispatchEvent(new Event('change'))`를 인위적으로 트리거하여 RC 주소 입력창이 즉각적으로 노출되거나 숨겨지도록 해결함.

---
*최종 작성일: 2026-07-06*
