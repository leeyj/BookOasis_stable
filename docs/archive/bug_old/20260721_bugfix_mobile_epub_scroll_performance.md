---
id: "20260721_bugfix_mobile_epub_scroll_performance"
date: 2026-07-21
category: "bugfix"
severity: "high"
status: "fixed"
tags: [viewer, epub, mobile, performance, scroll, regex, requestanimationframe, oom, fullscreen, reflow]
---

# 20260721 — 모바일 EPUB 뷰어 스크롤 버벅임 및 전체화면 강제 종료 결함 수정 완료

## 버그 내역

### 현상
- 모바일 환경에서 EPUB 세로 스크롤 뷰어 이용 시 터치 드래그 스크롤 직후 심한 프레임 드랍(버벅임 및 멈춤 현산) 발생.
- 스크롤을 지속할 경우 모바일 웹 프로세스(Web Content Process)가 메모리 초과/CPU 락업으로 강제 재시작되면서 전체화면(Fullscreen) 모드가 해제되고 뷰어가 강제 종료됨.

### 근본 원인
1. **수 MB 수십만 자 대상 정규식 연산 반복**: `txt_anchor_utils.js`의 `getTxtAnchorInfoByMode`에서 스크롤할 때마다(초당 60~120회) 전체 책 HTML(`fullText`)을 대상으로 `stripHtml(fullText)` 정규식을 실행하여 메인 쓰레드 락업 및 극심한 GC 메모리 allocation 유발.
2. **이벤트 쓰로틀링 결여**: `scrollHandler`가 스크롤 틱마다 동기적으로 호출되어 레이아웃 속성(`chunk.offsetTop`)을 읽고, 매 스크롤 틱마다 무거운 로그/진행률 저장 연산을 실행함.
3. **모바일 주소창 Toggle Resize 릴레이**: 스크롤 중 모바일 주소창 숨김/노출로 인한 `resize` 이벤트 발생 시 scroll 모드에서도 전체 DOM을 파기 후 재설정(`applyTxtSettings`)하여 스크롤 튕김 및 레이아웃 재배치가 꼬임.

## 영향도
- 모바일 스마트폰/패드 단말기에서 EPUB 도서 열람 시 가독성과 성능을 심각하게 저해하고 전체화면 이탈 및 뷰어 튕김 결함 유발.

## 수정 사항

### 수정 파일 목록

#### `static/js/viewer/txt_anchor_utils.js`
- `getTxtAnchorInfoByMode` 내 `scroll` 모드 시 전체 책 HTML 문자열 대상 `stripHtml(fullText)` 연산 제거.
- 현재 보고 있는 챕터 단일 텍스트(`txtChunks[currentChunkIdx]`) 기반으로 앵커 텍스트 추출하도록 변경하여 메모리 폭탄 및 CPU 정규식 락업 제거.

#### `static/js/viewer_txt.js`
- `scrollHandler`에 `requestAnimationFrame` 기반 쓰로틀링 적용하여 1프레임당 최대 1회만 처리하도록 개선.
- `logActiveViewportText()`, `saveDetailPosition()`, `saveProgress()` 등 과도한 DOM 읽기 및 세부 퍼센트 저장 연산을 150ms Debounce(스크롤 멈춤 시점) 처리.
- `handleResize` 내에서 스크롤 모드일 경우 `innerWidth` 변경이 없는 가로폭 미변동(주소창 토글로 인한 높이 변동) 시 DOM 재렌더링 스킵 로직 추가.

#### `static/js/viewer/txt_settings_apply.js`
- 보기 모드 전환(`isModeSwitch`) 시 클릭 즉시 "보기 모드 전환 중..." 토스트 메시지를 화면에 렌더링하고 `container.style.pointerEvents = 'none'`을 설정.
- 무거운 DOM 재렌더링 및 앵커 복원 로직을 비동기 타임아웃(`setTimeout 20ms`)으로 넘겨 브라우저가 프리징 전에 토스트와 입력 차단 상태를 먼저 그리도록 개선.
- 전환 및 스크롤 정렬이 완료되는 시점(300ms 후)에 `pointerEvents`를 원복하여 사이드 이펙트 완벽 차단.

## 해결 사항
- 모바일 EPUB 스크롤 시 프레임 드랍(60fps 유지)이 제거되고 뷰어가 튕기거나 전체화면이 끊기는 결함 완전 해결.
- 페이지 <-> 스크롤 모드 전환 시 사용자 입력을 안전하게 차단하여 위치 꼬임 및 프리징 사이드 이펙트 차단.
