---
title: "만화 뷰어 페이지 전환 시 로딩창 깜빡임(Flickering) 현상 개선"
project: "BookOasis"
category: "improvement"
date: 2026-06-21
tags: [improvement, javascript, frontend, viewer, delay]
---

# 🎨 만화 뷰어 페이지 전환 시 로딩창 깜빡임(Flickering) 현상 개선

## 1. 개선 내역 및 요청 사항
- **요청 사항**: 만화 뷰어에서 다음/이전 페이지 전환 시 찰나의 순간 동안 검은색 로딩창이 번쩍이며(깜빡거리며) 화면 흐름을 방해하는 불편함 개선.
- **조치 사항**: 이미지 로드 즉시 로딩창을 띄우지 않고, 300ms 동안 대기 타이머를 작동시켜 고속 로딩 시에는 로딩창 노출을 스킵하고 즉각 페이지를 갱신하도록 처리.

## 2. 영향도
- **영향 범위**: 만화 ZIP 뷰어 페이지 로드 흐름 (`static/js/viewer_comic.js`)
- **우선순위**: 보통 (사용성/UX 체감 갱신)

## 3. 변경 상세 내용
- **수정 소스 파일**: `static/js/viewer_comic.js`
- **조치 내용**:
  `loadComicPage()` 함수가 실행될 때 즉시 `showViewerLoading()`을 띄우던 기존 코드를 제거하고, `setTimeout`을 사용해 300ms 지연 타이머(`comicLoadingTimer`)를 설정하였습니다.
  - 300ms 이내에 `onload` 이벤트가 발생하면 `clearTimeout`으로 타이머를 무효화하여 로딩창이 아예 표시되지 않도록 보장합니다.
  - 네트워크 병목 등으로 로딩에 300ms를 초과해 지연될 경우에만 정상적으로 `showViewerLoading`을 작동시킵니다.
  - `onload` 및 `onerror` 시작부에 타이머 취소 루틴을 바인딩하여 안전한 클리너 구조를 구성하였습니다.

## 4. 해결 사항 및 검증 결과
- 수정 후 `deploy.py`를 통해 원격 배포 및 재구동을 진행하였고, 사용자가 직접 만화 뷰어에서 E2E 검증을 진행하기로 확인하였습니다.
