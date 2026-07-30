---
title: "Lazy 표지 스캐너 즉시 실행 버튼 인터페이스 추가"
project: "BookOasis"
category: "feature"
date: 2026-06-22
tags: [lazy-scanner, ui, settings, cron]
---

# Lazy 표지 스캐너 즉시 실행 버튼 인터페이스 추가

## 1. 개선 내역
- 일반 환경설정의 'Lazy 표지 스캐너 구동 주기(크론식)' 입력란 옆에 **[지금 실행]** 버튼을 신설하여, 백그라운드 크론 주기와 상관없이 관리자가 원할 때 언제든지 즉각적으로 표지 복원 백그라운드 태스크를 트리거할 수 있도록 UI를 개선했습니다.

## 2. 영향도
- **영향 범위**: 일반 환경설정 화면 (`static/js/settings/general.js`, `templates/components/tab_media_library.html`), 백엔드 관리자 API (`api/admin.py`, `static/js/api.js`)
- **개선 효과**: 신규 도서 추가 또는 원격 드라이브 재마운트 등으로 표지가 빠진 책이 발생했을 때 크론 스케줄을 기다릴 필요 없이 즉석에서 1권당 3초 간격의 무점착 표지 추출 태스크를 수동으로 기동할 수 있습니다.

## 3. 수정 사항
- **수정 소스 파일**: 
  - [api/admin.py](file:///c:/project/media_server/api/admin.py): `/api/media/settings/trigger-lazy-scan` 비동기 기동 API 신설
  - [static/js/api.js](file:///c:/project/media_server/static/js/api.js): `triggerLazyScan` 클라이언트 API 바인딩 추가
  - [static/js/settings/general.js](file:///c:/project/media_server/static/js/settings/general.js): `triggerLazyScanNow` 윈도우 전역 함수 매핑 및 토스트 성공 메시지 표시 구현
  - [templates/components/tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html): `setting-lazy-scan-cron` 인풋 우측에 `지금 실행` 버튼 마크업 추가

## 4. 해결 사항
- 이제 환경설정 탭에서 간편하게 버튼 클릭 한 번으로 Lazy 스캐너를 실시간 수동 실행 가능합니다.
