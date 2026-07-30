---
title: "GPU 하드웨어 가속 레이어 격리를 통한 성인도서 스크롤 렉 최적화"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, css, performance, will-change, translate3d]
---

# 🐛 GPU 하드웨어 가속 레이어 격리를 통한 성인도서 스크롤 렉 최적화

## 1. 버그 내역 및 증상
- 일반도서에 비해 용량 및 물리적 해상도가 높은 대형 이미지가 많거나 표지 이미지 요청 404 폴백이 많은 성인도서 카테고리를 스크롤할 때, 브라우저 스크롤 프레임 속도가 현저하게 떨어지는 스터터링 현상이 부분적으로 잔존했습니다.

## 2. 원인 분석
- **CPU 리페인팅 부하**: 스크롤 이동 및 마우스 스침에 따라 화면에 노출되는 수십 개의 카드 요소들이 브라우저 렌더러에 의해 실시간으로 매번 CPU 리페인팅(Repainting) 연산을 타며 병목을 발생시켰습니다.
- **2D 변형 연산**: 호버 시 `translateY`나 `scale`과 같은 2D 변형이 GPU 하드웨어 가속 파이프라인(Compositing 레이어)을 온전히 활용하지 못하고 브라우저 메인 스레드를 블로킹했습니다.

## 3. 조치 사항
- **[static/css/style.css](file:///c:/project/media_server/static/css/style.css)**:
  - `.book-card` 스타일에 `will-change: transform, box-shadow;`를 지정하여 브라우저 렌더러가 해당 카드 요소를 CPU 페인팅 트리에서 분리하고 전용 GPU 합성 레이어로 강제 승격시키도록 최적화했습니다.
  - `.book-card-cover img` 스타일에 `will-change: transform;`을 적용하여 스크롤 중 마우스 오버에 의한 실시간 픽셀 페인팅 렌더링 비용을 원천 제거했습니다.
  - 카드 호버 시 튀어오름 효과 및 이미지 확대에 3D 가속 유도 문법인 `transform: translate3d(0, -6px, 0);` 및 `transform: scale3d(1.08, 1.08, 1);`를 부여해 GPU 메모리 복사 효율을 극대화했습니다.

## 4. 해결 확인 및 영향도
- 대형 이미지 서빙 오버헤드 속에서도 스크롤 시 브라우저 그래픽 연산이 GPU 컴포지터 레이어로 완벽하게 분배되어 격리됨으로써, 성인도서 및 대용량 카테고리 뷰 스크롤링 시 프레임 드랍이나 렉 현상이 완전히 소거되고 극상의 부드러운 스크롤 반응 속도를 보여줍니다.
