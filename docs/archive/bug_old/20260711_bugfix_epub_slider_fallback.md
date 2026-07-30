---
title: "EPUB 뷰어 하단 슬라이더 위치정보 연산 전 먹통 결함 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-11
tags: [bugfix, viewer, epub, seekbar]
---

# EPUB 뷰어 하단 슬라이더 위치정보 연산 전 먹통 결함 조치

## 1. 버그 내역 및 증상
- EPUB 도서를 열자마자 하단 오버레이 슬라이더바(SeekBar)를 조작할 때, 슬라이더 변경 이벤트가 트리거되었음에도 페이지가 전혀 이동하지 않고 그대로 멈춰있는 현상.

## 2. 원인 분석
- **Locations 연산 비동기 딜레이**: `Epub.js` 엔진의 특성상 책의 문자수와 가상 위치 리스트(`locations`)를 백그라운드에서 계산하는 데 시간이 소요됨(분량이 큰 책은 수초~십수초 이상).
- **폴백 누락**: `[runtime.js](file:///c:/project/media_server/static/js/viewer/epub/runtime.js)`의 `epubSliderChange` 함수는 `locations` 배열이 완전히 생성된 것을 전제로 퍼센티지 CFI(`cfiFromPercentage`)를 조회하도록 작성되어 있었음. 이에 따라 책을 연 지 얼마 되지 않은 시점에는 위치 조회가 실패하여 `cfi = null`이 되며 슬라이더 이동이 완전히 먹통이 됨.

## 3. 조치 사항
1. **스파인(Spine) 인덱스 매핑 폴백 구현 (`static/js/viewer/epub/runtime.js`)**:
   - `epubSliderChange()` 연산 시 `epubBook.locations.length` 가 존재하지 않거나 0인 상태(준비 중)일 때는, 책을 구성하는 스파인 파일(XHTML 파일) 목록의 전체 개수 대비 슬라이더의 백분율 비율을 계산하여 target 인덱스를 추출하도록 설계함.
   - 해당 target 스파인 경로(`items[targetIndex].href`)로 rendition을 즉시 전시하도록 안전장치를 적용하여, 연산 완료 전에도 대략적인 챕터 영역으로 즉각 반응 이동하도록 조치함.

## 4. 해결 확인 및 영향도
- EPUB 도서 진입 직후 위치 연산(Locations)이 완료되기 전에도, 하단 슬라이더를 통해 임의의 퍼센트로 이동하면 챕터 단위로 오차 없이 즉시 페이지가 연동 갱신됨.
