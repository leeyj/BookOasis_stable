---
title: "이미지 로드 에러(404) 시 대체 로딩 루프 및 스크롤 성능 저하 버그 수정"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [image-onerror, scroll-performance, rendering, infinite-loop]
---

# 🧠 이미지 로드 에러(404) 시 대체 로딩 루프 및 스크롤 성능 저하 버그 수정

## 1. 개요 및 버그 내용
- **현상**: 표지가 깨진 책(커버 파일 부재 등으로 404가 나는 도서)이 목록에 많을 때, 카테고리를 이동하거나 스크롤을 내릴 때 마우스 휠 스크롤 프레임이 심하게 드랍(끊김)되고 전체 페이지 로딩 속도가 늦어지는 현상.
- **영향**: 원활한 브라우징 경험을 방해하고, 불필요한 네트워크 요청 및 CPU 100% 병목 현상 발생.

## 2. 원인 분석
1. **리스트 그리드 `onerror` 누락**: [`ui.js`](file:///c:/project/media_server/static/js/ui.js)의 책 카드 내 `<img>` 태그에 `onerror` 속성이 누락되어 스크롤을 내릴 때마다 깨진 표지를 가진 카드들이 계속 서버에 `/covers/...` 404 요청을 큐잉하여 네트워크 리소스를 고사시킴.
2. **`onerror` 무한 재귀 루프**: [`modal.js`](file:///c:/project/media_server/static/js/modal.js)의 상세 정보 패널 이미지들(`volume-thumb`, `detail-cover-sm`)의 `onerror` 핸들러가 대체 주소를 지정해 주고 있으나, `this.onerror = null;` 처리가 부재함. 이로 인해 인터넷 연결 상태가 불량하거나 오프라인인 경우 대체 이미지마저 404가 나면서 `onerror` 핸들러가 다시 작동해 **무한 재귀 요청 루프**가 발생하고, 자바스크립트 싱글 스레드를 100% 점유해 휠 스크롤 끊김 병목을 초래함.

## 3. 조치 내용
1. **목록 그리드에 `onerror` 핸들러 추가 ([`ui.js`](file:///c:/project/media_server/static/js/ui.js))**:
   - `createBookCard` 내 책 커버 이미지 태그에 `onerror="this.onerror=null; this.src='[대체이미지주소]';"`를 새로이 매핑하여 이미지 404 에러 시 로컬 Unsplash 북커버 플레이스홀더 이미지로 즉각 대체하고, 2차 실패 시 무한 루프를 방지하게 조치.
2. **`onerror` 무한 루프 차단 ([`modal.js`](file:///c:/project/media_server/static/js/modal.js))**:
   - `detail-cover-sm` 및 `volume-thumb` 이미지의 `onerror` 속성 실행부 맨 처음에 `this.onerror=null;` 구문을 삽입하여 대체 이미지 로드 실패 시 이벤트 리스너를 즉각 폐기, 무한 반복 요청을 완전 봉쇄.

## 4. 결과 및 검증
- 수정 배포 완료 후 깨진 표지가 포함된 만화책 카테고리를 스크롤할 때 발생하던 프레임 끊김 현상이 완전히 해소됨을 확인.
- F12 네트워크 탭 관찰 시 동일한 깨진 이미지 리소스가 무한 재귀 요청되지 않고 1회 대체 후 안전하게 소거됨을 확인.
