---
title: "스캔 완료 토스트 메시지가 사라지지 않는 잔상 고착 결함 조치"
category: "bugfix"
date: 2026-07-22
severity: "low"
affected_files:
  - "static/js/view_manager.js"
tags: [toast, ui, animation, timer]
---

# 스캔 완료 토스트 메시지가 사라지지 않는 잔상 고착 결함 조치

## 1. 버그 개요
- 시리즈 스캔 또는 도서 상세 스캔 완료 후 화면 하단에 렌더링되는 **"스캔이 완료되었습니다. 화면을 새로 고칩니다."** 토스트 알림창이 3초가 지나도 사라지지 않고 화면 하단에 계속 고착되는 현상.

## 2. 원인 분석
- `view_manager.js`의 `showToast()`에서 기존 `window.toastTimer` 타이머가 새로고침 및 DOM 재렌더링 시점에 취소(`clearTimeout`)된 상태에서 애니메이션 스타일(CSS `opacity: 1`, `transform`)이 완전히 리셋되지 않은 채 잔상으로 남음.

## 3. 수정 사항
- `static/js/view_manager.js`:
  - `showToast()` 호출 즉시 기존 `toastTimer`를 명시적으로 정리(`clearTimeout` & `null` 초기화).
  - DOM 컨테이너 렌더링 시 `opacity = '0'`과 위치를 먼저 강제 리셋 후 2중 `requestAnimationFrame`을 통해 깨끗하게 등장 애니메이션을 적용.
  - 3초 후 `opacity = '0'`으로 투명화 은닉 애니메이션 보장.

## 4. 검증 결과
- 단권 및 시리즈 스캔 완료 후 토스트 메시지가 정상적으로 등장했다가 3초 후 애니메이션과 함께 완전히 사라지는 것을 확인함.
