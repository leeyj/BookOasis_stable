---
title: "동적 SVG 표지 생성 API Nginx 라우팅 오류 및 구형 기본 이미지 노출 버그 수정"
category: "bugfix"
date: 2026-07-23
severity: "medium"
affected_files:
  - "README.md"
  - "README_EN.md"
  - "docs/guide_installation.md"
  - "docs/guide_installation_en.md"
  - "static/js/ui.js"
  - "static/js/detail_render.js"
  - "static/js/metadata_search.js"
tags: [nginx, fallback-cover, svg, onerror, default-cover]
---

# 버그 내역

## 증상

Nginx 적용 환경에서 표지가 없는 도서(또는 404 커버) 로딩 시, 새로 도입된 모던 동적 SVG 커버 대신 구형 정적 기본 이미지(`/static/images/default_cover.jpg`: 책이 펼쳐진 사진)가 노출되는 현상.

## 근본 원인 분석

1. **Nginx의 `/covers/` alias 룰이 동적 SVG 생성 API(`/covers/fallback`)를 가로챔**
   - Nginx의 `location /covers/ { alias .../covers/; }` 설정으로 인해 `/covers/fallback?title=...` 백엔드 파이썬 API 라우트 요청이 백엔드로 전송되지 않고 Nginx 디스크 정적 파일로 처리되어 `404 Not Found`가 발생.
2. **프론트엔드의 구형 default_cover.jpg 2차 튕김**
   - 브라우저가 `/covers/fallback`에서 404를 수신하자 `img.onerror` 이벤트가 발동하여 2차 Fallback인 구형 펼쳐진 책 사진(`/static/images/default_cover.jpg`)으로 튕겨서 렌더링됨.

---

## 수정 사항

1. **Nginx 설정 및 설치 가이드 문서 보완**
   - `location /covers/fallback` 백엔드 프록시 라우트 조항을 `location /covers/` 정적 서빙 상단에 배치하여 `/covers/fallback` 요청이 파이썬 백엔드로 정확히 전달되도록 수정.
2. **프론트엔드 이미지 onerror 핸들러 모던화 (`static/js/ui.js`, `detail_render.js`, `metadata_search.js`)**
   - `onerror` 발동 시 구형 default_cover.jpg 로 튕기던 코드를 inline SVG data URI (`buildTextCoverDataUri`)로 대체.
   - Nginx 미적용 상태나 네트워크 이상 시에도 구형 이미지 노출 없이 모던 벡터 SVG 표지가 100% 보장됨.

---

## 해결 결과

- 표지가 없는 도서 로딩 시 어떠한 경우에도 구형 펼쳐진 책 사진이 노출되지 않고 고급스러운 모던 SVG 벡터 이미지 커버가 안전하게 렌더링됨.
