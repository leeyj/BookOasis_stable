---
title: "모바일 브라우저 정적 캐시 우회를 위한 뷰어 CSS 캐시 버스터 버전 업그레이드"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, mobile, cache, cache-buster, static, css]
---

# 🐛 모바일 브라우저 정적 캐시 우회를 위한 뷰어 CSS 캐시 버스터 버전 업그레이드

## 1. 버그 정의 및 원인
- **현상:** 모바일 크롬 브라우저 등에서 뷰어 하단 가림 버그 패치가 적용되었음에도 불구하고, 화면상에서 뷰어 하단 레이아웃이 전혀 변경되지 않은 이전 캐시 상태로 고착되어 있는 현상 발생.
- **원인:**
  - `templates/components/tab_media_library.html` 내부에서 `tab_media_library_viewer.css` 스타일을 로드할 때 캐시 버스터 스트링이 `?v=1.2.0`으로 정적 유지되고 있었음.
  - 이로 인해 모바일 기기 브라우저가 새롭게 변경된 스타일 시트를 무시하고 브라우저 캐시에 상주하던 이전 CSS를 계속하여 재사용함.

## 2. 해결 방안
- 뷰어 CSS의 캐시 버스터 꼬리표 버전을 **`?v=1.2.1`**로 업그레이드하여, 모바일 클라이언트 브라우저들이 업데이트된 스타일 명세를 강제 다운로드(Force Bypass Cache) 하도록 유도함.

## 3. 수정 사항 (수정 소스 파일 목록)
- **[templates/components/tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**
  - 3라인 `tab_media_library_viewer.css` 링크의 버전 쿼리를 `v=1.2.1`로 갱신함.

## 4. 해결 사항 및 E2E 검증 결과
- **캐시 자동 무력화:** 캐시 버스터 식별자 변경 후 원격 NAS 배포 및 재시동을 수행하여, 모바일 크롬 등의 강제 캐시 삭제 조작 없이도 정상적으로 새 뷰어 CSS가 로드되어 하단 레이아웃 가림이 완벽히 수정 반영되는 것을 E2E 수동 검증 완료함.
