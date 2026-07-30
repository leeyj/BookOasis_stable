---
title: "도서 그리드 CSS 렌더링(MIME 타입 및 backdrop-filter) 소거를 통한 상/하방 스크롤 렉 최적화"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, css, scroll-performance, backdrop-filter, reflow]
---

# 🐛 도서 그리드 CSS 렌더링(MIME 타입 및 backdrop-filter) 소거를 통한 상/하방 스크롤 렉 최적화

## 1. 버그 내역 및 증상
- 무한 스크롤 마진을 조정한 이후에도, 그리드 화면을 위로 올리거나(상방) 내릴 때(하방) 화면이 매끄럽지 않고 미세하게 떨리며 버벅거리는 잔 렉(스터터링 현상)이 지속적으로 발생하는 현상입니다.

## 2. 원인 분석
- **대량의 중첩 backdrop-filter 부하**: 각 책 카드의 모서리 상단에 달라붙는 뱃지 스타일(`.book-badge-count`)에 `backdrop-filter: blur(4px);` 속성이 지정되어 있었습니다. 화면에 수십 개씩 카드가 존재하면 브라우저가 스크롤할 때마다 이 뱃지 뒷배경 레이아웃에 대해 대량의 실시간 GPU 블러링 픽셀 연산을 중복으로 계산해야 하므로 프레임 드랍이 걸렸습니다.
- **광범위한 transition 오버헤드**: `.book-card` 스타일에 `transition: all 0.3s`가 걸려있어, 스크롤 이동 도중 마우스 포인터가 카드들을 스쳐 지나갈 때마다 불필요하게 모든 CSS 속성 변화에 대한 애니메이션 연산이 유발되었습니다.

## 3. 조치 사항
- **[static/css/style.css](file:///c:/project/media_server/static/css/style.css)**:
  - 뱃지(`.book-badge-count`) 스타일 내 고비용 GPU 연산인 `backdrop-filter: blur(4px);` 속성을 완전히 제거했습니다. 대신 딤 효과 가독성을 위해 불투명도를 `background: rgba(15, 23, 42, 0.95);`로 소폭 강화했습니다.
  - 카드의 transition을 `all` 대신 `transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;` 로 좁혀 리플로우/리페인트 성능 비용을 최소화했습니다.

## 4. 해결 확인 및 영향도
- 대량의 하드웨어 가속 필터 연산이 소거되고 애니메이션 트랙이 단순화됨에 따라 스크롤을 어느 방향으로 굴리든 끊김이나 스터터링 없이 완전히 부드러운 스크롤 성능이 보장됩니다.
