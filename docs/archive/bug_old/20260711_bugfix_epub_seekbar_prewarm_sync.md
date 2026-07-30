---
title: "EPUB 뷰어 시크바 잠김 및 백그라운드 런타임 예외 결함 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-11
tags: [bugfix, viewer, epub, seekbar]
---

# EPUB 뷰어 시크바 잠김 및 백그라운드 런타임 예외 결함 조치

## 1. 버그 내역 및 증상
- EPUB 도서 진입 시 35% 등의 읽던 곳 복원 시도가 정상 포착되었음에도 시크바가 여전히 `max="1"`로 잠겨서 슬라이더 조작이 차단되고 반응이 없는 현상.
- 브라우저 개발자 도구 콘솔에 `[Viewer-Epub] Background locations generation failed: TypeError: Cannot read properties of undefined (reading 'currentLocation')` 에러 로그가 확인됨.

## 2. 원인 분석
- **초기화 미완료 시점의 API 호출**: `ensureLocations` 연산이 백그라운드에서 완료되었을 때, `rendition` 의 아이프레임이 DOM 상에 완전히 활성화되기 전에 `rendition.currentLocation()` 메서드를 성급하게 호출하여 내부의 `manager` 객체가 `undefined` 로 파싱되며 `TypeError` 가 발생함.
- **오류로 인한 UI 업데이트 차단**: 위 예외가 스레드 실행을 중단시켜 하단 시크바 동기화 로직(`updateProgressPercent`)의 동작을 가로막음.
- **사전 동기화 부재**: locations 연산이 다 끝나기 전에는 시크바 범위를 퍼센트(`0~100`) 형태로 리셋하여 열어두는 초기 시크바 강제 설정이 누락되어 있어 `max="1"` 로 계속 잠겨 있었음.

## 3. 조치 사항
1. **런타임 호출 안전성 검증 (`static/js/viewer/epub/page_mode.js`)**:
   - `page_mode.js` 백그라운드 콜백에서 `rendition.currentLocation()` 호출 전에 `rendition.manager` 가 완벽하게 준비되어 있는지 사전 검증을 부여하고, 전체 연산을 `try-catch` 블록으로 두껍게 감싸 런타임 에러 전파로 인한 UI 차단 문제를 해결함.
2. **시크바 사전 동기화(Pre-warm Sync) 도입 (`static/js/viewer/epub/epub_progress.js`)**:
   - `restoreEpubProgress()` 에서 위치 연산 완료 대기 전에 우선 복원한 진척도 퍼센트(`scrollPercent`)를 활용하여 `syncEpubSeekBar()` 를 먼저 선제 강제 호출함. 이를 통해 슬라이더의 `min=0, max=100, value=percent` 범위를 초기에 즉시 세팅해 주어 시크바 잠금을 해제함.

## 4. 해결 확인 및 영향도
- EPUB 도서 진입 시 런타임 오류가 완전히 소거되었으며, locations 연산 유무와 상관없이 시크바가 즉각 `100` 최대치로 활성화되어 드래그가 정상 작동함.
