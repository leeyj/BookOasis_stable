---
title: "iOS Safari WebKit 대시보드 로딩 버벅임 및 GPU 레이어 폭증 최적화"
category: "bugfix"
date: 2026-07-23
severity: "medium"
affected_files:
  - "static/css/style.css"
  - "static/js/ui.js"
tags: [dashboard, ios, webkit, performance, gpu, css, lazyload]
---

# 버그 내역

## 증상

대시보드 페이지 로딩 및 스크롤 시 iOS Safari(WebKit) 환경에서 극심한 프레임 드랍과 화면 버벅임(Stuttering)이 발생하는 반면, 안드로이드 삼성 브라우저(Chromium/Blink) 환경에서는 매우 부드럽게 로딩되는 성능 격차 현상.

## 영향도

- **대상**: iOS Safari 및 WebKit 기반 모바일 브라우저
- **심각도**: Medium — 안드로이드 대비 iOS 기기에서 대시보드 로딩 및 카드 렌더링 시 스크롤 감도 및 UI 반응 속도 저하

---

## 원인 분석

1. **iOS WebKit의 `will-change` 오남용에 의한 GPU 메모리 고갈**:
   - `static/css/style.css` 내 `.book-card` 및 `.book-card-cover img`에 상시 부여되어 있던 `will-change: transform, box-shadow;`로 인해, iOS WebKit은 대시보드의 모든 카드 요소를 개별 독립 하드웨어 가속 레이어(Compositing Layer)로 동시 승격시킴.
   - 20~50개 이상의 카드가 대시보드에 배치되면서 수십 개의 레이어가 무겁게 생성되고 GPU 메모리 폭증 및 레이어 스래싱(Layer Thrashing) 현상으로 메인 UI 스레드 정체 발생.

2. **이미지 동기 디코딩에 의한 메인 스레드 블로킹**:
   - 대량의 책 커버 이미지 로드 시 동기 디코딩으로 인해 렌더링 파이프라인에서 순간적인 프레임 스킵(Jank)이 발생함.

---

## 수정 사항

### 1. `static/css/style.css`
- `.book-card` 및 `.book-card-cover img`에 설정되어 있던 상시 `will-change` 속성을 제거하여 WebKit 엔진이 불필요한 Compositing Layer를 남발하지 않도록 수정.

### 2. `static/js/ui.js`
- `createBookCard` 함수 내 커버 이미지 `<img>` 요소에 `decoding="async"` 및 `loading="lazy"` 속성을 강화하여 이미지 로드 및 디코딩 연산을 비동기 처리하도록 개선.

---

## 해결 결과

- iOS Safari에서도 독립 GPU 레이어 생성이 최소화되어 대시보드 로딩 및 수평/수직 스크롤 시 프레임 드랍 없이 부드럽고 쾌적한 렌더링 속도 확보.
- 안드로이드 및 iOS 모두 동일하게 부드러운 반응속도 및 로딩 경험 제공.
