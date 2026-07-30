---
title: "일반 환경설정 저장 시 proxyAuth 정의 누락 버그 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, settings, general]
---

# 🧠 [Bugfix] 일반 환경설정 저장 시 proxyAuth 정의 누락(ReferenceError) 오류 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 환경설정 ➡️ 일반 환경설정 탭
- **장애 현상**: 일반 환경설정 값을 변경하거나 저장 버튼(`submitGeneralSettings`)을 누르면 설정이 저장되지 않고 브라우저 개발자 도구(F12) 콘솔에 `설정 저장 에러: ReferenceError: proxyAuth is not defined` 오류가 노출되며 설정 저장에 실패함.

---

## 2. 영향도 분석 (Impact Analysis)
- 일반 환경설정의 모든 설정 필드(썸네일 크기, 페이지 로드 제한, 폰트 크기, DB 풀 크기 등)를 사용자가 수정하여 저장할 수 없는 상태에 빠져, 전반적인 사이트 구성 및 리더 뷰어 환경을 변경하는 기능이 작동하지 않는 심각한 UX 차질을 빚음.

---

## 3. 원인 파악 (Root Cause)
- `static/js/settings/general.js` 내 `submitGeneralSettings` 함수에서 `api.updateSystemSetting('PROXY_HEADER_AUTH', proxyAuth)` API 호출을 수행하고 있으나, 함수 상단에서 DOM 요소(`setting-proxy-header-auth`)로부터 `proxyAuth` 값을 읽어오는 변수 정의 단계(`const proxyAuth = ...`)가 누락되어 `ReferenceError`가 발생한 것이 원인임.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [general.js](file:///c:/project/media_server/static/js/settings/general.js#L120-L125)
- `submitGeneralSettings` 함수 내부 변수 선언 영역에 DOM으로부터 `setting-proxy-header-auth` 엘리먼트의 값을 안전하게 추출하는 구문을 추가함.

```javascript
// 수정 전
  const hideCompleted = document.getElementById('setting-hide-completed-in-history')?.checked ? '1' : '0';
  const rcloneRcUrl = document.getElementById('setting-rclone-rc-url')?.value || 'http://localhost:5572';

// 수정 후
  const hideCompleted = document.getElementById('setting-hide-completed-in-history')?.checked ? '1' : '0';
  const proxyAuth = document.getElementById('setting-proxy-header-auth')?.value || '0';
  const rcloneRcUrl = document.getElementById('setting-rclone-rc-url')?.value || 'http://localhost:5572';
```

---

## 5. 최종 검증 (Verification)
- 환경설정 페이지 진입 후 일반 환경설정의 값들을 변경하고 `저장`을 클릭했을 때 더 이상 `ReferenceError`가 발생하지 않고, 환경설정이 성공적으로 저장되어 반영되었다는 토스트 창이 정상 표시됨을 확인하였습니다.
