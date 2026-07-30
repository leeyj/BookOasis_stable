---
title: "비-만화책(PDF, EPUB, TXT) 뷰어 내 수동 읽음 완료 오작동 수정"
date: "2026-07-06"
type: "bugfix"
status: "completed"
tags: ["viewer", "overlay", "mark_completed"]
---

# 비-만화책(PDF, EPUB, TXT) 뷰어 내 수동 읽음 완료 오작동 수정

## 1. 개요 및 증상
- **현상**: 사용자가 도서 뷰어 상단 오버레이 메뉴에서 [읽음 완료] 버튼을 누를 때 만화책(ZIP/CBZ)의 경우에는 완독 저장이 잘 되지만, PDF, EPUB, TXT 등의 도서를 읽던 중 버튼을 클릭하면 아무 동작도 하지 않는(먹통) 현상이 발생했습니다.

## 2. 원인 분석
- 뷰어 오버레이 UI(`media_viewer.html`)에 명시된 `markAsCompleted()` 전역 함수는 본래 만화책(ZIP) 컨트롤러(`viewer_comic.js` 및 `navigation.js`) 전용으로 하드코딩 바인딩되어 있었습니다.
- 만화책 컨트롤러 내에 정의된 기존 `markAsCompleted` 함수는 `Renderer.comicTotalPages` 와 같은 만화책 전용 상태 변수가 `0`보다 클 때만 동작하도록 분기 처리가 닫혀 있어, PDF/EPUB/TXT의 경우에는 클릭 자체가 완전히 무시되었습니다.

## 3. 해결 방안
- [viewer.js](file:///c:/project/media_server/static/js/viewer.js): 뷰어 코어 조율기에 **통합 `markAsCompleted()` 함수**를 구현하고, 전역 `window.markAsCompleted`에 덮어씌워 바인딩했습니다.
  - **ZIP/CBZ 포맷**: 기존에 검증된 만화책 전용 함수(`markComicAsCompleted`)를 그대로 중계 호출합니다.
  - **PDF 포맷**: `#pdf-page-info` 레이블 돔에서 마지막 페이지 정보를 실시간으로 파싱하여 마지막 인덱스를 강제 인젝션 전송합니다.
  - **EPUB 포맷**: 고정 100분율로 진척도를 저장하여 전송합니다.
  - **TXT 포맷**: 뱃지 정보 `#comic-overlay-page-info` 에 표시된 전체 텍스트 청크 수(예: `/ 15`)를 정규식으로 안전하게 파싱하여 마지막 청크 인덱스를 저장 전송합니다.
- 저장 후 완료 안내 얼럿창(`viewer.read_completed`)을 제공하고 오버레이 컨트롤 바를 자동으로 닫기 처리하여 마감합니다.

## 4. E2E 검증 결과
- TXT, EPUB 및 PDF 뷰어 내에서 상단 오버레이 컨트롤의 [읽음 완료] 버튼을 클릭했을 때, 수동 완독 전송이 실시간으로 수행되며 완료 팝업 안내창이 잘 뜹니다.
- 뷰어를 닫고 목록으로 나왔을 때, 해당 도서들의 상태가 100% 완독 완료로 즉각 변경 표기되어 리프레시되는 것을 최종 확인했습니다.
