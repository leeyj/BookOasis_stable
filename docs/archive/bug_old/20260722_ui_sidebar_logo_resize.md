---
title: "사이드바 BookOasis 브랜드 로고 크기 50% 확대 (22px -> 32px)"
category: "ui"
date: 2026-07-22
severity: "low"
affected_files:
  - "templates/components/tab_media_library.html"
tags: [ui, sidebar, brand, logo_size]
---

# 사이드바 BookOasis 브랜드 로고 크기 50% 확대 (22px -> 32px)

## 1. 수정 개요
- 좌측 상단 사이드바의 BookOasis 브랜드 파비콘 로고가 시각적으로 작게 느껴졌던 점을 보완하여 크기를 기존 **22px에서 32px (약 50% 확대)**로 선명하고 또렷하게 키웠습니다.

## 2. 주요 수정 사항
- **[templates/components/tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**
  - 로고 `<img style="width: 32px; height: 32px;">`로 변경 및 여백 밸런스 조정.

## 3. 검증 결과
- 좌측 상단 BookOasis 텍스트 타이틀과 조화롭게 정렬되며 브랜드 로고 아이콘의 가독성과 선명도가 개선됨을 확인함.
