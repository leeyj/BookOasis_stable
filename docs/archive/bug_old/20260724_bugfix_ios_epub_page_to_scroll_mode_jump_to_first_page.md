---
title: iOS EPUB/TXT 페이지 모드에서 스크롤 모드로 전환 시 첫 페이지(0px) 튕김 버그 수선
date: 2026-07-24
tags: [ios, epub, txt-viewer, view-mode-transition, anchor-restore, webkit]
---

# 🐛 iOS EPUB/TXT 페이지-스크롤 모드 전환 시 첫 페이지 튕김 버그 수선

## 1. 개요 및 영향도
- **이슈 항목**: iOS(Safari/WebKit 환경) 모바일에서 EPUB/TXT 도서 감상 중 페이지 모드 ➔ 스크롤 모드로 전환 시, 이전에 읽던 위치가 유지되지 않고 무조건 0번째/첫 페이지(`scrollTop = 0`)로 튕기는 현상.
- **영향 범위**: iOS WebKit 기반 브라우저 전체 (iPhone, iPad Safari 및 iOS 크롬). Android 및 PC 크롬에서는 정상 작동했으나 iOS의 렌더링/Reflow 지연 특성으로 발생.

---

## 2. 근본 원인 분석 (Root Cause)
1. **iOS Safari `scrollLeft` 획득 왜곡**:
   - iOS WebKit에서는 CSS Columns 수평 스크롤 컨테이너일 때, 뷰포트 레이아웃 계산 타이밍에 따라 `scrollWrapper.scrollLeft` 를 동기적으로 읽어오면 `0` 으로 왜곡 반환되어 앵커 텍스트가 첫 0번째 페이지 텍스트로 잘못 캡처됨.
2. **DOM Reflow(Layout Offsets) 재계산 지연**:
   - `scrollMode` 가 `'scroll'` 로 변경되며 DOM(`contentArea.innerHTML`)이 새로 구성된 직후, Android/PC와 달리 iOS WebKit은 150ms 시점까지 `matchedElem.offsetTop` 을 `0` 으로 반환하여 `scrollWrapper.scrollTop` 이 `0` 으로 결정되는 구조적 시차(Reflow Delay) 발생.

---

## 3. 수선 내역 (Fix Details)

### A. iOS WebKit 전용 뷰포트 엘리먼트 앵커 캡처 보완 (`static/js/viewer/txt_anchor_utils.js`)
- 페이지 모드에서 앵커 텍스트 캡처 시 `scrollLeft` 읽기 실패를 대비하여, `document.elementFromPoint` 를 활용해 **뷰포트 중앙에 실제 가시 노출되고 있는 DOM 엘리먼트 텍스트 30자를 1순위로 직접 추출**하도록 강화.

### B. iOS Reflow 지연 방어 2차 래치(SafeGuard Latch) 적용 (`static/js/viewer/txt_settings_apply.js`)
- 스크롤 모드 전환 시 1차 앵커 복원 수행 후, iOS WebKit의 Layout Reflow 타임아웃을 감안하여 **+120ms 후 2차 래치(Latch) 검증**을 자동 실행.
- 만약 1차 시점에 `scrollTop` 이 `0` 으로 잡혔을 경우, 2차 래치 시점에 올바르게 재계산된 `offsetTop` 과 `txt-scroll-chunk` 오프셋 좌표로 **위치를 100% 정밀 재정렬**하여 첫 페이지 튕김을 원천 차단.

---

## 4. 검증 결과
- iOS WebKit 및 Android/PC 환경에서 EPUB 페이지 모드 ➔ 스크롤 모드 전환 시, 읽던 문단 및 챕터 위치로 100% 정밀 복원됨을 확인.
