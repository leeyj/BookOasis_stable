---
title: "TXT/EPUB 뷰어 페이지 모드 우측 글자 삐져나옴(Bleed) 스크롤 박스 구조적 결함 조치"
category: "bugfix"
date: 2026-07-25
severity: "high"
affected_files:
  - "static/js/viewer/txt_settings_apply.js"
tags: [txt_viewer, epub_viewer, multi_column, page_bleed, scroll_box_clipping, bugfix]
---

# 🐛 버그 수정 내역: TXT/EPUB 뷰어 페이지 모드 우측 글자 삐져나옴 스크롤 박스 구조적 결함 조치

## 증상

TXT/EPUB 뷰어의 페이지 넘김 모드(`scrollMode === 'page'`)에서 모바일 또는 특정 패딩(Padding) 설정 적용 시, 화면 오른쪽 여백 영역으로 다음 페이지(2번째 컬럼)의 텍스트가 삐져나와 가로로 잘린 채 비치는 현상이 남아있음.

---

## 근본 원인 분석

1. **CSS 가로 스크롤 컨테이너 패딩(`paddingRight`) 조작의 구조적 한계**:
   - 기존 구현에서는 `scrollWrapper`에 `paddingLeft: 20px`, `paddingRight: 20px`를 직접 부여하고 `scrollWrapper` 너비를 뷰포트 전체(100%, 예: 360px)로 설정했습니다.
   - 자식 엘리먼트(`contentArea`)는 320px마다 다단 컬럼을 생성하므로, 2번째 컬럼의 오프셋 시작 위치는 `x = 340px` (좌측 패딩 20px + 1번째 컬럼 320px)가 됩니다.
   - 그러나 CSS 표준상 `overflow-x: auto` 컨테이너의 `paddingRight`는 스크롤을 끝까지 보냈을 때 생기는 여백일 뿐, `scrollLeft = 0` 위치에서 시작 지점의 자식 오버플로우를 잘라내어 감추지 못하므로 `340px~360px` 공간에 2번째 컬럼 텍스트가 그대로 노출되었습니다.

---

## 수정 및 구조 개선 사항

1. **`static/js/viewer/txt_settings_apply.js`**:
   - `scrollWrapper` 자체의 `paddingLeft`와 `paddingRight`를 항상 **`0`**으로 초기화하고, `scrollWrapper`의 폭(`width`)을 패딩이 차감된 실제 타겟 표시 너비(`safeTargetWidth = Math.max(260, parentWidth - (padLeft + padRight))`)로 1:1 밀착 지정.
   - `scrollWrapper`를 `margin-left: auto; margin-right: auto;`로 배치하여 좌/우 여백은 `scrollWrapper` 바깥의 부모 컨테이너 중앙 정렬로 처리.
   - `scrollWrapper`의 뷰포트 영역(예: 320px) 밖으로 벗어나는 모든 2번째 컬럼 이상의 텍스트가 `overflow-x: auto` 영역 외부로 완전히 차단되어 **우측 비침(Bleeding) 현상이 100% 근본적으로 완전 해결됨**.

---

## 해결 사항

- 모바일 디바이스 및 데스크톱 환경에서 패딩 조절 시 화면 우측 끝에 다음 페이지 글자가 노출되던 현상이 완전히 제거됨.
- 1장 및 2장 보기 스냅 페이징이 1px의 어긋남 없이 정밀하게 정렬됨.
