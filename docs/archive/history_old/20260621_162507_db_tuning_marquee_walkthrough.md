---
title: Walkthrough - db_tuning_marquee
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 워크쓰루: 만화 뷰어 페이지 전환 시 로딩창 깜빡임(Flickering) 현상 개선

만화책을 넘길 때 순간적으로 로딩창이 번쩍이며 독서 흐름을 저해하는 현상을 해결하기 위해, 타임아웃 디바운스(300ms) 기법을 적용하여 빠른 로드 환경에서는 로딩창이 아예 표시되지 않도록 튜닝을 완료하였습니다.

## 변경 내용

### 1. 프론트엔드 뷰어 모듈 수정

#### [MODIFY] [viewer_comic.js](file:///c:/project/media_server/static/js/viewer_comic.js)
- `comicLoadingTimer` 변수를 추가하여 300ms 지연 타이머를 제어하도록 수정하였습니다.
- 페이지 전환 요청 시 즉각 `showViewerLoading`을 호출하지 않고, `setTimeout`으로 지연시켜 300ms 이후에도 완료되지 않았을 때만 화면 로딩창을 띄우며 이미지 투명도 처리를 하도록 바인딩하였습니다.
- `onload` 및 `onerror` 핸들러가 동작하는 시점에 `clearTimeout`을 호출하여, 300ms 이내 초고속 로드 성공 시 로딩 오버레이의 발생을 원천 차단하였습니다.

## 검증 결과

- 로컬 변경 내역 검증 후, 배포 스크립트 `python deploy.py`를 실행하여 원격 홈 서버(`192.168.0.20`) 배포를 완료하였습니다.
- 실물 UI 확인 및 세부 레이아웃 검증은 사용자가 직접 현업 환경에서 수동으로 E2E 테스트를 수행하기로 확인 및 완료하였습니다.
