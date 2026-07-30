---
title: "도서 그리드 목록 무한 스크롤 및 휠 스크롤 프레임 속도 최적화"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [scroll-performance, DocumentFragment, CSS, reflow]
---

# 🧠 도서 그리드 목록 무한 스크롤 및 휠 스크롤 프레임 속도 최적화

## 1. 개요 및 버그 내용
- **현상**: 무한 스크롤을 통해 도서 카드가 30개씩 추가 로드될 때 화면이 일시적으로 버벅거리고, 전체 카드가 늘어날수록 마우스 휠 스크롤 프레임이 눈에 띄게 저하(스터터링 현상)되는 현상 발생.

## 2. 원인 분석
1. **과도한 레이아웃 리플로우(Reflow)**: 기존 [`ui.js`](file:///c:/project/media_server/static/js/ui.js)의 렌더러들은 신규 30개의 카드를 로드할 때 `container.appendChild`를 매 카드마다 1회씩, 즉 **총 30번을 순차적으로 직접 DOM에 호출**함. 이로 인해 브라우저 렌더러가 30회 연속 리플로우를 수행하며 버벅임 병목 발생.
2. **GPU 연산 과부하 (`backdrop-filter`)**: 기존 [`tab_media_library_grid.css`](file:///c:/project/media_server/static/css/tab_media_library_grid.css)의 `.book-card` 클래스에 `backdrop-filter: blur(10px);` 속성이 걸려 있었음. backdrop-filter는 요소의 하위 영역을 실시간으로 캡처하고 픽셀 셰이더를 통해 흐리게 흐트러트리는 연산 비용이 가장 큰 CSS 속성 중 하나임. 카드가 누적될수록 픽셀 흐림 효과 연산 부하가 기하급수적으로 늘어 휠 스크롤 프레임이 파괴되는 원인으로 작용.

## 3. 조치 내용
1. **`DocumentFragment` 기반 일괄 렌더링 도입 ([`ui.js`](file:///c:/project/media_server/static/js/ui.js))**:
   - `appendBooksGrid`, `renderBooksGrid`, `renderHistoryGrid`, `renderDashboardHistory`, `renderDashboardRecentlyAdded` 5개 함수에서 생성된 엘리먼트 카드들을 가상 메모리 DOM 빌더인 `DocumentFragment` 객체에 먼저 추가한 뒤, 루프 종료 후 최종적으로 컨테이너에 단 1번만 일괄 `appendChild` 하도록 리팩토링. 레이아웃 리플로우 횟수를 30회에서 1회로 극적 감소.
2. **고비용 CSS 속성 제거 ([`tab_media_library_grid.css`](file:///c:/project/media_server/static/css/tab_media_library_grid.css))**:
   - `.book-card` 스타일에서 `backdrop-filter: blur(10px);`를 영구 제거.
   - 불투명도를 보정하기 위해 `background` 속성값을 `rgba(30, 41, 59, 0.4)`에서 `rgba(30, 41, 59, 0.85)`로 가독성이 높은 색상으로 보완.

## 4. 결과 및 검증
- 수정한 사항을 원격 홈 서버에 배포 완료 및 기동 검증.
- 수백 권의 책이 노출되는 카테고리에서 휠 스크롤을 빠르고 길게 내려도 프레임 드랍 없이 극도로 미끄럽고 부드럽게 렌더링되며 스크롤되는 성능 최적화 성과를 확인.
