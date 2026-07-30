---
title: "EPUB 페이지-스크롤 모드 전환 시 슬라이더 프리징 결함 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-11
tags: [bugfix, viewer, epub, seekbar, layout]
---

# EPUB 페이지-스크롤 모드 전환 시 슬라이더 프리징 결함 조치

## 1. 버그 내역 및 증상
- EPUB 도서 감상 중 페이지 모드와 스크롤 모드를 상호 전환(클릭)하고 나면, 하단 슬라이더바가 굳어서 반응이 없거나 페이지가 넘어가지 않는(먹통) 현상.

## 2. 원인 분석
- **전환 시 ratio null화에 따른 업데이트 누락**: `[epub_settings.js](file:///c:/project/media_server/static/js/viewer/epub/epub_settings.js)` 내의 `applyEpubSettingsInternal` 함수는 모드 전환 시 기존 읽던 위치를 유지하기 위해 `preservePagePosition = true` 와 `preferResumeStart = true` 로 기동됨.
- 이 과정에서 렌더링에 사용할 임시 `ratio` 는 `null` 이 반환되어 최하단의 `updateProgressPercent(ratio * 100)` 구문 실행이 생략됨.
- 이에 따라 전환 후 UI 슬라이더의 `max`와 `value` 값이 새로운 전환 모드 규격(스크롤은 100%, 페이지는 locations 분량)에 맞추어 강제 리셋 갱신되지 못하고 꼬여 버려 슬라이더 조작 계통이 완전히 무력화되었음.

## 3. 조치 사항
1. **전환 시 슬라이더 강제 리셋 폴백 주입 (`static/js/viewer/epub/epub_settings.js`)**:
   - `applyEpubSettingsInternal` 의 최하단 갱신 연산 시 `ratio === null` 일 때의 예외 폴백 분기를 생성하여, 현재 저장되어 있는 진행률 퍼센트(`contextUpdated.currentScrollPercent`)를 활용해 `updateProgressPercent`를 강제 실행하도록 조치함.
   - 이를 통해 페이지<->스크롤 모드 간에 렌더러 인스턴스가 완전히 쪼개지고 새로 생성되더라도, 슬라이더 UI의 최대치(`100%`)와 현재 수치가 항상 올바르게 동기화 재정렬되도록 안정성을 확보함.

## 4. 해결 확인 및 영향도
- 페이지 모드와 스크롤 모드를 번갈아가며 수없이 전환하더라도, 전환이 마쳐진 즉시 슬라이더 바가 100% 진행률 구조로 올바르게 재바인딩되어 감상 및 이동 조작에 아무런 지연 없이 완벽히 연동됨.
