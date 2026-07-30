---
title: "좌측 상단 사이드바 타이틀 및 로고 아이콘 변경 (라이브러리 -> BookOasis)"
category: "ui"
date: 2026-07-22
severity: "low"
affected_files:
  - "templates/components/tab_media_library.html"
tags: [ui, sidebar, brand, logo, favicon]
---

# 좌측 상단 사이드바 타이틀 및 로고 아이콘 변경 (라이브러리 -> BookOasis)

## 1. 개요 및 변경 목적
- 좌측 상단 사이드바 헤더의 고정 폴더 아이콘 및 "라이브러리" 텍스트를 파비콘/고유 로고 이미지(`logo.png`)와 **"BookOasis"** 브랜드 명칭으로 교체하여 브랜드 정체성 및 깔끔함을 강화함.

## 2. 주요 수정 사항
- **[templates/components/tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**
  - `h3.sidebar-title` 요소 내부의 FontAwesome 폴더 아이콘과 텍스트를 고유 파비콘 로고 이미지 (`<img src="logo.png" style="width: 22px; height: 22px;">`)와 **"BookOasis"**로 수정.

## 3. 검증 결과
- 좌측 상단 사이드바 헤더 위치에 파비콘 로고와 함께 BookOasis 브랜드 명이 정갈하게 노출됨을 확인.
