---
title: "브랜드 로고 이미지 뒷면 네온 발광 효과(drop-shadow) 필터 전량 제거"
project: "BookOasis"
category: "improvement"
date: 2026-06-29
tags: [brand, logo, style, css, filter, bugfix]
---

# 🎨 브랜드 로고 이미지 뒷면 네온 발광 효과(drop-shadow) 필터 전량 제거

## 1. 개선 내역
- **현상**: 로고 에셋 도입 후 뒷면에 적용된 네온 발광 효과(`filter: drop-shadow`)가 사각형 배경 박스 경계선에 걸려 반사되면서, 어둡고 미니멀한 대시보드 테마와 이질감을 발생시키고 둥둥 뜨는 시각적 결함 유발.

## 2. 영향 범위
- 로그인 템플릿 (`templates/login.html`)
- 설정 페이지 템플릿 (`templates/components/views/library_settings.html`)

## 3. 수정 사항
- **CSS 스타일 수정**:
  - `login.html` 및 `library_settings.html` 내 로고 이미지 엘리먼트(`<img>`)의 인라인 스타일에서 `filter: drop-shadow(...)` 설정을 전량 삭제함.
  - 사각형 형태가 도드라져 보이지 않도록 모서리를 부드럽게 감싸주는 `border-radius: 8px;` (로그인) 및 `border-radius: 12px;` (어바웃) 옵션을 덧붙여 마감 완성도를 보완함.

## 4. 해결 사항
- 사각형 이미지 경계선을 따라 발생하던 부자연스러운 네온 발광 잔상이 완전히 걷히고, 어두운 백그라운드 색상과 일체화되어 로고가 훨씬 정돈되고 가라앉은 고급스러운 형태로 렌더링됨.
