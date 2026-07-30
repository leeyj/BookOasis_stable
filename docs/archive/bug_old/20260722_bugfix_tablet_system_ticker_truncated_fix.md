---
title: "태블릿 뷰포트 하단 시스템 속보(system-ticker) 가려짐 및 절단 결함 조치"
category: "bugfix"
date: 2026-07-22
severity: "low"
affected_files:
  - "static/css/mobile.css"
tags: [css, tablet, system_ticker, z_index, viewport]
---

# 태블릿 뷰포트 하단 시스템 속보(system-ticker) 가려짐 및 절단 결함 조치

## 1. 버그 개요
- 태블릿(iPad 등) 기기 화면에서 백그라운드 스캔이 진행될 때 하단에 출현하는 **[시스템 속보]** 푸터 바(`system-ticker-footer`)가 화면 최하단 오버레이 레이어 미세 조정 부족으로 반쯤 가려지거나 텍스트가 잘리는 현상.

## 2. 수정 사항
- `static/css/mobile.css`:
  - `.system-ticker-footer`의 태블릿 및 모바일(width 1200px 이하) 반응형 스타일 오버라이드 강화.
  - `left: 0 !important;`, `width: 100% !important;`, `z-index: 10005 !important;`, `bottom: env(safe-area-inset-bottom, 0px) !important;`를 적용하여 뷰포트 최하단 레이어 위로 가려짐 없이 선명하게 정렬 배치.

## 3. 검증 결과
- 태블릿 뷰포트에서 백그라운드 스캔 실행 시 하단 시스템 속보 바가 잘림이나 겹침 없이 100% 명확하게 노출됨을 확인함.
