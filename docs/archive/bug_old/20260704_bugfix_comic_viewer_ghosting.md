---
name: comic_viewer_ghosting_fix
description: 만화 뷰어 전환 시 이전 로드 이미지가 잔상처럼 튀어 노출되는 고스팅 버그 조치
---

# 🐛 [버그수정] 만화 뷰어 전환 시 이전 책 이미지 잔상(Ghosting) 노출 문제

만화책을 감상한 뒤 뷰어를 닫고, 다른 시리즈의 만화책을 선택해 볼 때 이전 책의 마지막 렌더링 화면이 수밀리초~수초 동안 잔상처럼 먼저 깜빡이며 보이다가 새로운 책의 첫 페이지로 넘어가는 레이아웃 고스팅 현상을 조치했습니다.

## 1. 버그 분석 및 영향도
* **원인**: 만화 뷰어 종료 시 (`closeMediaViewer`), 뷰어의 도서별 정리 함수가 호출되나 만화 포맷(Comic)의 경우 뷰어 DOM 콘텐츠(`.comic-image-wrapper` 내의 `<img>` 요소들) 및 진행 중인 이미지 로딩 타이머(`comicLoadingTimer`)를 초기화(Clean)해주는 명시적인 해제 로직이 누락되어 있었습니다. 이 때문에 뷰어가 닫힌 상태에서도 이전 렌더링 노드가 DOM 트리 상에 온전히 남아 있다가, 다른 책을 불러와 새 렌더러가 구동되어 `innerHTML = ''`을 실행하기 직전 찰나에 뷰어 모달이 뜨면서 이전 책 이미지가 그대로 화면에 비추어지는 어색한 UX 버그를 유발했습니다.
* **영향 범위**: 만화(ZIP, CBZ) 포맷 리더 전체

## 2. 해결 방법
만화 뷰어 종료 시 렌더링 노드를 완벽히 정리하는 생명주기 관리 함수 `clearComicViewer`를 설계 및 적용했습니다.
1. **[renderer.js](file:///c:/project/media_server/static/js/viewer/renderer.js)**:
   * `.comic-image-wrapper` DOM 컨테이너 내부의 `innerHTML`을 비우고, 페이지 변경 사항을 추적하던 `IntersectionObserver` 인스턴스를 즉시 해제(`disconnect()`)하며, 작동 중이던 `comicLoadingTimer`도 `clearTimeout`하여 잔류 타이머로 인한 로딩 지연 오작동을 차단하는 `clearComicViewer()` 함수를 신규 구현 및 Export 처리했습니다.
2. **[viewer_comic.js](file:///c:/project/media_server/static/js/viewer_comic.js)**:
   * 하위 모듈(`renderer.js`)에서 불러온 `clearComicViewer` 기능을 Re-export 하고, 레거시 호환 및 전역 조작을 위해 `window.clearComicViewer` 글로벌 바인딩을 추가했습니다.
3. **[viewer.js](file:///c:/project/media_server/static/js/viewer.js)**:
   * 뷰어 코어 종료 이벤트인 `closeMediaViewer` 실행 흐름 초입에 타 포맷 클리어 로직(`clearEpubViewer()`, `clearPdfViewer()`)과 더불어 `clearComicViewer()`를 명시적으로 실행하여 뷰어가 닫히는 즉시 이전 만화 렌더링 이미지와 잔상 데이터를 완벽하게 클리어하도록 보장했습니다.

## 3. 수정 파일 목록
* [static/js/viewer/renderer.js](file:///c:/project/media_server/static/js/viewer/renderer.js#L449-L463)
* [static/js/viewer_comic.js](file:///c:/project/media_server/static/js/viewer_comic.js#L26-L51)
* [static/js/viewer.js](file:///c:/project/media_server/static/js/viewer.js#L143-L149)
