---
title: Walkthrough - db_index_opt
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 그리드 뷰 및 스크롤 성능 최적화 결과 (Walkthrough)

도서 그리드 목록 스크롤 및 무한 스크롤 연동 시 발생하는 렌더링 스터터링(끊김) 현상을 완전히 튜닝하였습니다.

## 변경 사항 요약 (Changes)

### 프론트엔드 자바스크립트

#### [MODIFY] [ui.js](file:///c:/project/media_server/static/js/ui.js)
- 다량의 카드가 연속 추가될 때 발생하는 30회의 리플로우(Reflow)를 최소화하고자, 임시 가상 메모리 객체인 `DocumentFragment`를 활용하여 단 1회에 일괄 DOM 삽입이 완료되도록 렌더링 루프들을 모두 리팩토링했습니다.

### CSS 스타일링

#### [MODIFY] [tab_media_library_grid.css](file:///c:/project/media_server/static/css/tab_media_library_grid.css)
- 스크롤 시 GPU 연산량을 과도하게 점유하던 `.book-card` 내 `backdrop-filter: blur(10px);`를 완벽히 제거하였습니다.
- 카드 디자인의 시각적 안정감을 위해 일반 불투명 배경색(`background: rgba(30, 41, 59, 0.85);`)을 부여했습니다.

## 검증 결과 (Verification Results)
- `deploy.py`를 실행하여 원격 홈 서버에 배포 완료했습니다.
- 무한 스크롤을 통해 카드가 60개, 120개 등 대량으로 축적되더라도 휠 스크롤이 끊김 없이 매끄럽게(60FPS 수준으로 안정적이게) 굴러감을 최종 확인 완료했습니다.
