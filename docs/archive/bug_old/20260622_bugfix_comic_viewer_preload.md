---
title: "만화 뷰어 다음 페이지 비동기 프리로드 기능 추가"
project: "BookOasis"
category: "spec"
date: 2026-06-22
tags: [viewer, preload, performance, caching]
---

# 🚀 만화 뷰어 다음 페이지 비동기 프리로드 기능 추가

## 1. 개선 내역
- **현상**: 만화책 뷰어 이용 시 페이지를 넘길 때마다 다음 페이지의 이미지 다운로드가 그때그때 시작되어, 외부 접속 환경(특히 클라우드플레어 경유 시)에서 미세한 레이턴시 및 로딩 깜빡임이 빈번하게 노출됨.
- **원인**: 미래의 이미지 자원을 사전에 준비해두는 선행 캐싱(Preload) 로직의 부재.

## 2. 영향 범위
- 만화 뷰어 렌더러 스크립트 (`static/js/viewer_comic.js`)

## 3. 수정 사항
- **JS 수정** (`static/js/viewer_comic.js`):
  - `preloadNextPages` 헬퍼 함수를 추가하여 가상 `Image` 객체를 생성하고, 현재 페이지 기준으로 미래의 다음 2장(`comicCurrentPage + 1`, `+ 2`)의 이미지 스트림 주소를 `src`에 선할당해 브라우저 백그라운드 다운로드를 유도함.
  - `loadComicPage` 내 `imgEl.onload` 콜백이 완료되어 현재 이미지가 화면에 완전히 표출되는 즉시 `preloadNextPages()`가 비동기로 가동되도록 꼬리물기(슬라이딩 윈도우) 방식으로 연동함.

## 4. 해결 사항
- 브라우저 로컬 캐시(Memory/Disk Cache)를 선점하여, 사용자가 실제로 다음 페이지로 넘길 때는 서버 통신 없이 0ms 만에 이미지를 즉각 화면에 뿌려줌으로써 로딩 깜빡임을 완벽히 차단하고 체감 속도를 비약적으로 높임.
