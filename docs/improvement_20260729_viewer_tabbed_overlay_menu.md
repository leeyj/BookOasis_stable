---
title: "뷰어 컨텍스트 오버레이 메뉴 부문별 탭 개편 및 푸른색 테마 적용"
date: 2026-07-29
category: improvement
tags: [viewer, ui, overlay, tabs, theme, blue_accent]
impact: medium
status: completed
---

# 개선 내역: 뷰어 컨텍스트 오버레이 메뉴 부문별 탭 개편 및 푸른색 테마 적용

## 개요
뷰어 중앙 클릭/터치 시 나타나는 컨텍스트 오버레이 메뉴를 기존의 2행 나열 방식에서 **4개 부문별 탭(Tab) 구조**로 전면 개편하고, 대시보드의 기본 테마(보라색)와 시각적으로 확연히 식별되도록 **푸른색(Blue) 계통 테마 디자인 시스템**을 도입하였습니다.

## 주요 변경 사항

### 1. 부문별 4개 탭 헤더 및 컨텐츠 구조화 (`templates/components/media_viewer.html`)
- **`[🧭 이동]` (Navigation)**: 처음부터, 마지막으로, 읽음 완료
- **`[📖 보기]` (Layout)**: 페이지/연속 스크롤, 1장/2장 보기, 진행방향(LTR/RTL), 높이/너비 맞춤, 스크롤 이미지 너비
- **`[✍️ 스타일]` (Typography)**: 폰트, 글자 크기(A-/A+), 행간 조절, 단락 간격, 테마 전환 (TXT/EPUB 전용)
- **`[📐 여백]` (Margins)**: 상하좌우 여백(Padding Top/Bottom/Left/Right) 실시간 슬라이더 조절 패널 통합
- **하단 고정 시크바**: 어떤 탭으로 전환하더라도 하단 시크바 슬라이더 및 페이지 번호 뱃지는 항상 고정 표시하여 페이지 이동 편의성 보존

### 2. 푸른색 계통 테마 및 Glassmorphism CSS 적용 (`static/css/tab_media_library_viewer.css`)
- 대시보드의 메인 보라색 accent (`#a855f7`)와 직관적으로 차별화되도록 블루 사파이어/에메랄드 톤 (`#3b82f6`, `#2563eb`, `#38bdf8`) 적용
- 탭 버튼, 맞춤 모드 active 스타일, 오버레이 테두리 glow 및 슬라이더 썸/트랙 푸른색 디자인 스타일링

### 3. 동적 탭 전환 및 포맷별 감춤 제어 JS (`static/js/viewer/navigation.js`, `viewer_padding.js`)
- `switchViewerOverlayTab(tabName)` 스크립트를 신설하여 탭 선택 클릭 시 부드럽게 컨텐츠를 전환
- 미디어 포맷(만화/PDF vs TXT/EPUB)을 자동 감지하여 스타일 탭의 노출/은닉을 자동 제어

## 효과 및 검증
- 기존에 한 공간에 밀집해 있던 뷰어 옵션들이 직관적인 4개 탭으로 정리되어 모바일 및 데스크톱 환경에서 옵션 찾기가 매우 쉬워졌습니다.
- 대시보드의 보라색 메인 테마와 상반되는 푸른색(Blue Accent) 뷰어 테마가 적용되어 오버레이 메뉴 활성화 상태를 한눈에 식별할 수 있습니다.
