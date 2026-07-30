---
title: Walkthrough - infinite_scroll_fix
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 도서 목록 무한 스크롤 미동작 버그 수정 결과 (Walkthrough)

우측 도서 목록에서 스크롤을 하단까지 내렸을 때 무한 스크롤을 통한 다음 페이지 로드 처리가 먹통이 되던 요인을 수정 완료했습니다.

## 변경 사항 요약 (Changes)

### 프론트엔드 라이브러리 코어

#### [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
- `window.addEventListener('scroll')` 내부의 스크롤 감지 높이 구산식을 `window.pageYOffset`, `document.body.scrollTop` 및 `window.innerHeight`를 전방위 호환하도록 수정하여 브라우저 기기별 렌더 파편화 문제를 극복했습니다.
- 하단 로딩 트리거 마진을 150px에서 200px로 증가시켜 로드 반응 속도를 개선하였으며, 환경설정(`settings`) 페이지가 노출되어 로딩 대상 목록이 부재할 시에는 무한 스크롤이 트리거되지 않도록 방어 로직을 구성했습니다.

## 검증 결과 (Verification Results)
- 변경 소스 적용 후 `deploy.py`를 실행하여 원격 홈 서버에 배포하고 데몬을 재구동하였습니다.
- 다량의 도서가 포함된 책장 카테고리를 선택한 뒤 하단으로 휠 스크롤 시, 스크롤바가 하단 부근에 닿았을 때 정상적으로 페이징 연동이 개시되어 추가 도서들이 하단에 연쇄 로드 및 출력되는 것을 수동 검증 완료하였습니다.
