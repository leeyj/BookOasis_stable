---
title: "기본 도서 표지 외부 CDN 의존성 제거 및 로컬 정적 이미지 전환"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [default-cover, fallback-image, static-assets, optimization]
---

# 🧠 기본 도서 표지 외부 CDN 의존성 제거 및 로컬 정적 이미지 전환

## 1. 개요 및 버그 내용
- **현상**: 표지가 깨진 도서의 대체 이미지로 Unsplash CDN 주소(`https://images.unsplash.com/...`)를 동적으로 다운로드하여 사용하고 있었음.
- **문제점**:
  - 오프라인 홈 서버 환경이나 인터넷 속도가 느린 환경에서 디폴트 표지 이미지가 정상적으로 출력되지 않고 엑스박스로 노출됨.
  - 외부 CDN 네트워크 왕복 시간으로 인해 로딩 딜레이 발생.

## 2. 원인 분석
- [`ui.js`](file:///c:/project/media_server/static/js/ui.js)와 [`modal.js`](file:///c:/project/media_server/static/js/modal.js)의 이미지 경로 및 `onerror` 대체 경로가 모두 외부 Unsplash URL 주소로 직접 하드코딩되어 외부 네트워크망에 종속되어 있었음.

## 3. 조치 내용
1. **로컬 리소스 저장**:
   - `static/images/` 폴더를 신설하고, 기존 Unsplash 책 표지 고화질 이미지를 PowerShell `Invoke-WebRequest`를 사용해 로컬 정적 파일 [`static/images/default_cover.jpg`](file:///c:/project/media_server/static/images/default_cover.jpg)로 다운로드 및 배치 완료.
2. **프론트엔드 코드 교체**:
   - `static/js/ui.js` 및 `static/js/modal.js` 파일 내의 모든 Unsplash URL 참조값(총 6군데)을 로컬 정적 주소인 `/static/images/default_cover.jpg`로 일제히 치환 조치.

## 4. 결과 및 검증
- 원격 홈 서버에 배포 완료 및 Gunicorn 데몬 재시작 성공.
- 표지가 없는 도서(깨진 표지 책) 로딩 시, 외부 인터넷 패킷을 발생시키지 않고 로컬 서버의 캐시 파일(`/static/images/default_cover.jpg`)에서 즉각 이미지를 뿌려주므로 오프라인 환경 호환성 및 화면 렌더링 체감 속도가 획기적으로 상승한 것을 검증 완료.
