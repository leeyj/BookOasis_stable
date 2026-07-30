---
title: "EPUB 보기 모드(스크롤/페이지) 전환 시 오작동 및 첫 장 이동 오류 수정"
date: "2026-07-06"
type: "bugfix"
status: "completed"
tags: ["viewer", "epub", "scroll-mode"]
---

# EPUB 보기 모드(스크롤/페이지) 전환 시 오작동 및 첫 장 이동 오류 수정

## 1. 개요 및 증상
- **현상**: EPUB 뷰어 감상 도중 보기 형식을 '페이지 보기' ➔ '스크롤 보기' (또는 그 반대)로 스위칭할 때, 기존에 읽던 위치가 유지되지 않고 첫 페이지로 강제 튕겨 나가거나 본문 영역이 흰 화면으로 깨지며 제대로 표시되지 않고 진행률 저장이 더 이상 되지 않는 먹통 버그가 발생했습니다.

## 2. 원인 분석
- **`relocated` 이벤트 유실**: `changeEpubScrollMode` 함수가 구동될 때 기존 `epubRendition` 인스턴스를 `destroy()`한 뒤 새 인스턴스를 바인딩하지만, 새 인스턴스에 진행률 저장(`saveProgress`)과 시크바 동기화(`syncEpubSeekBar`)를 매핑하는 **`relocated` 이벤트 리스너를 다시 등록해 주는 과정이 누락**되었습니다.
- **렌더링 잔재 꼬임**: `epubBook.renderTo()` 가 기동될 때 이전 돔(Iframe 객체 등)이 깨끗하게 정리되지 않은 채 새로운 렌더링 컨텍스트가 주입되어 레이아웃 오작동이 유발되었습니다.

## 3. 해결 방안
- [viewer_epub.js](file:///c:/project/media_server/static/js/viewer_epub.js):
  - `epubRendition.destroy()` 직후 `#epub-render-area` 컨테이너의 내부 HTML을 강제 초기화(`innerHTML = ''`)하여 렌더러가 중첩되거나 충돌하지 않도록 보장했습니다.
  - 새 `epubRendition` 객체가 재생성되는 즉시 `relocated` 리스너를 명시적으로 재등록(Re-bind)하여 모드 변경 이후의 스크롤/페이지 이동 시에도 진행률 데이터와 시크바 썸 위치가 정상적으로 연동되도록 보완했습니다.

## 4. E2E 검증 결과
- EPUB 도서 감상 중 페이지 보기 모드에서 스크롤 보기 모드로 전환 시, 이전 감상 지점(CFI)이 100% 매끄럽게 유지되며, 스크롤 이동 및 조작 중에도 시크바 백분율과 진행률이 정확히 동기화 보존되는 것을 E2E 테스트 확인했습니다.
