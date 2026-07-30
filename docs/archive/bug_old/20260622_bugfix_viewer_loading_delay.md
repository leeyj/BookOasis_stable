---
title: "만화 뷰어 로딩창 지연 타이머 설정 기능 구현"
project: "BookOasis"
category: "bug"
date: 2026-06-22
tags: [viewer, bugfix, config, latency]
---

# 🐛 만화 뷰어 로딩창 깜빡임 개선 및 설정 기능 추가

## 1. 버그/개선 내역
- **현상**: 직접 IP 접속 시에는 캐싱 완료 후 로딩창이 전혀 노출되지 않으나, 클라우드플레어 + 리버스 프록시 환경에서 접속하는 경우 이미지 로드 지연으로 인해 로딩창이 잠깐 나타났다 사라지는 깜빡임 현상이 발생함.
- **원인**: `viewer_comic.js`에 이미지 다운로드 로딩 지연 한계점(Timeout)이 `300ms`로 고정되어 있음. 외부 접속 환경에서는 네트워크 레이턴시(TTFB 지연) 및 TCP 전송 시간 때문에 로드가 완료되는 시간이 300ms를 수시로 초과하게 되어 로딩창 노출 타이머가 실행됨.

## 2. 영향 범위
- 전체 환경설정 내 일반 설정 탭 UI (`templates/components/tab_media_library.html`)
- 일반 설정 저장 및 로드 컨트롤러 (`static/js/settings/general.js`)
- 만화 뷰어 로딩 제어 컨트롤러 (`static/js/viewer_comic.js`)

## 3. 수정 사항
- **HTML 수정** (`templates/components/tab_media_library.html`):
  - 환경설정 -> 일반 설정 탭 폼 하단에 **만화 뷰어 로딩 지연 시간 (ms)** 설정 필드(`setting-comic-loading-delay`)를 새롭게 배치함.
- **JS 수정** (`static/js/settings/general.js`):
  - `loadGeneralSettings` 실행 시 `localStorage`에 저장되어 있는 `comic_loading_delay` 값을 폼의 인풋에 동기화함.
  - `submitGeneralSettings` 실행(설정 저장 버튼 클릭) 시 입력값을 로컬 스토리지에 즉시 반영 및 영구 보존하도록 처리함.
- **JS 수정** (`static/js/viewer_comic.js`):
  - `loadComicPage` 함수 내 이미지 로드 타이머 생성 시 `localStorage.getItem('comic_loading_delay')`를 조회하여 설정 시간을 동적으로 적용함. (설정값이 없을 시 기본값 `300ms` 사용)

## 4. 해결 사항
- 브라우저에 설정 값을 저장함으로써 사용자가 자신의 인터넷 대역폭 상태(로컬망, 외부망, 모바일 데이터 등)에 맞춰 타임아웃 지연 시간을 수동 조정할 수 있도록 조치함.
- 로컬스토리지를 활용하여 서버의 별도 DB 스키마 수정 및 추가 API 개발 없이 안정적으로 개인화 설정을 유지하도록 처리함.
