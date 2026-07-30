---
title: Walkthrough - localize_default_cover_image
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 기본 도서 표지 로컬 이미지 전환 결과 (Walkthrough)

외부 CDN(Unsplash)에 의존하던 기본 책 표지 리소스를 로컬 정적 디렉터리로 완전히 가져와 폐쇄망 지원 및 로딩 성능을 고도화했습니다.

## 변경 사항 요약 (Changes)

### 정적 리소스 (Assets)
- `static/images/` 폴더를 새로이 구성하고, Unsplash의 기본 이미지를 `default_cover.jpg` 파일명으로 로컬 영구 적재 완료했습니다.

### 프론트엔드 코드
- [`ui.js`](file:///c:/project/media_server/static/js/ui.js) 및 [`modal.js`](file:///c:/project/media_server/static/js/modal.js) 내의 기존 외부 Unsplash URL 참조값들을 전부 로컬 서버 절대 경로인 `/static/images/default_cover.jpg`로 일제 변경했습니다.

## 검증 결과 (Verification Results)
- `deploy.py`를 실행하여 원격지 배포 및 Gunicorn 데몬 재시작 성공을 확인했습니다.
- 표지가 없는 도서(404 에러 책) 렌더링 시, 지연 시간이나 엑스박스 노출 현상 없이 로컬 서버에 등록된 `/static/images/default_cover.jpg` 이미지가 즉시 초고속 서빙됨을 수동 검증 완료했습니다.
