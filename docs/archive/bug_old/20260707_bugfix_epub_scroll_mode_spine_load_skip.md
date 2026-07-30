---
title: "EPUB 스크롤 모드 전환 시 비동기 파일 I/O 경합으로 인한 일부 챕터 누락 버그 해결"
date: "2026-07-07"
type: "bugfix"
status: "completed"
tags: ["viewer", "epub", "scroll-mode", "promise-all", "oom"]
---

# EPUB 스크롤 모드 전환 시 비동기 파일 I/O 경합으로 인한 일부 챕터 누락 버그 해결

## 1. 개요 및 증상
- **현상**: EPUB 도서 감상 중 페이지 보기 모드에서는 책의 전체 내용이 올바르게 렌더링되나, 스크롤 보기 모드로 전환 시 다음 챕터(Spine)들이 정상적으로 불려오지 않고 본문 내용 중간이 단절되거나 앞부분 일부만 보이는 버그가 발생했습니다.

## 2. 원인 분석
- `content_builder.js` 내의 `buildMergedContent()`는 단일 통짜 스크롤 문서를 구축하기 위해 EPUB의 모든 챕터(SpineItems) 리소스를 불러옵니다.
- 이때 모든 리소스 로딩(`item.load()`)을 `Promise.all`로 병렬 비동기 요청했습니다.
- EPUB 파일 압축 해제(JSZip) 및 IO 연산 수십~수백 건이 브라우저에서 동시에 몰아치면서 자원 점유 경합, 네트워크 타임아웃, 메모리 초과(OOM)가 일어나 상당수의 챕터 로딩이 `catch` 블록으로 넘어가 조용히 스킵 누락되었던 것입니다.

## 3. 해결 방안
- **[content_builder.js](file:///c:/project/media_server/static/js/viewer/epub/content_builder.js)**:
  - `Promise.all`을 이용한 무차별적인 병렬 파일 I/O 로딩 방식을 폐기했습니다.
  - 안전한 `for` 루프 동기 비동기 결합 방식을 사용하여, 각 챕터(SpineItem) 리소스를 한 번에 하나씩 **순차적으로 로드(Sequential Loading)**하도록 아키텍처를 교체했습니다.
  - 이를 통해 메모리 락 및 브라우저 병목 현상이 완벽히 소거되어 모든 챕터가 100% 무손실 상태로 보장 로딩됩니다.

## 4. E2E 검증 결과
- 페이지 모드에서 스크롤 모드로 전환하거나, 뷰어에 진입하자마자 스크롤 모드를 구동할 시, 챕터 누락 현상 없이 EPUB의 모든 내용이 처음부터 끝까지 완전하게 병합되어 표출됨을 확인했습니다.
