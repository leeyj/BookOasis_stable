---
title: "EPUB 본문 내부 링크 클릭 시 외부 페이지 이동으로 인한 500 에러 해결"
date: "2026-07-07"
type: "bugfix"
status: "completed"
tags: ["viewer", "epub", "link", "navigation", "500-error"]
---

# EPUB 본문 내부 링크 클릭 시 외부 페이지 이동으로 인한 500 에러 해결

## 1. 개요 및 증상
- **현상**: EPUB 책을 읽던 중 각주(footnote) 또는 목차 링크 등 본문 내부 하이퍼링크(`<a>`)를 클릭했을 때, 뷰어가 크래시 나며 백엔드 서버(Flask)가 500 에러를 반환하고 뷰어가 꺼지거나 에러 화면으로 이동하는 버그입니다.

## 2. 원인 분석
- 뷰어 돔에 챕터를 직접 삽입하는 스크롤 모드 상태에서 `<a>` 링크 클릭을 가로채지 않아, 브라우저가 해당 상대 경로 주소(예: `http://localhost:5930/Chapter02.xhtml`)로 **페이지 이동(URL Navigation)**을 수행했습니다.
- 백엔드에 존재하지 않는 잘못된 주소가 다이렉트로 날아가 500 에러를 유발한 것입니다.

## 3. 해결 방안
- **[interactions.js](file:///c:/project/media_server/static/js/viewer/epub/interactions.js)**:
  - 뷰어 렌더 영역(`renderArea`) 클릭 이벤트 캡처 리스너에 **링크 가로채기(Link Hijack)** 코드를 추가했습니다.
  - 내부 파일 상대 링크인 경우 브라우저 자체 이동(`e.preventDefault()`, `e.stopPropagation()`)을 즉시 차단합니다.
  - 타겟 ID 해시를 기반으로 현재 통합 스크롤 문서 내부에서 해당 위치를 찾아 부드럽게 스크롤 동기화(`scrollIntoView`)를 수행하도록 연결시켰습니다.

## 4. E2E 검증 결과
- 본문 내 각주 링크나 목차 연결을 클릭했을 때, 500 에러 팝업이나 화면 이탈 없이 스크롤이 해당 링크 목적지로 정확하고 신속하게 이동함을 확인했습니다.
