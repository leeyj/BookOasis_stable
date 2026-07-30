---
title: "EPUB/TXT 목처 대체 명칭('1장', '2장') 변경 및 비표준 EPUB 목차 파서 강화"
category: "bugfix"
date: 2026-07-25
severity: "low"
affected_files:
  - "static/js/viewer/txt_toc.js"
  - "static/i18n/ko.json"
  - "static/i18n/en.json"
  - "services/text_epub_content_service.py"
tags: [epub_toc, chapter_fallback, non_standard_epub, ncx_parsing, bugfix]
---

# 🐛 버그 및 기능 개선 내역: EPUB/TXT 목차 대체 명칭("1장", "2장") 변경 및 비표준 EPUB 목차 파서 강화

## 증상

목차(NCX/NAV) 메타데이터가 없는 TXT/EPUB 도서이거나 비표준 구조로 제작된 EPUB 파일에서 뷰어 우측 목차(TOC) 패널을 열었을 때, 목록 항목이 `"청크 1"`, `"청크 2"`와 같은 기계적인 표현으로 표시되는 문제.

---

## 원인 분석

1. **프론트엔드 목차 대체 명칭 하드코딩**:
   - `txt_toc.js`에서 서버로부터 목차 목록(`tocList`)을 받지 못했을 때 `"청크 ${idx + 1}"`로 하드코딩된 개발용 문자열을 생성함.

2. **비표준 EPUB 목차 탐색 제한**:
   - `text_epub_content_service.py`에서 OPF manifest에 `media-type="application/x-dtbncx+xml"` 또는 `properties="nav"`가 정확히 지정되지 않았거나, NCX XML 파싱 시 대소문자/네임스페이스 차이(`navMap` vs `navmap`)가 있을 경우 탐색이 누락되어 빈 목차 목록(`[]`)이 반환됨.

---

## 수정 사항

1. **프론트엔드 (`static/js/viewer/txt_toc.js`)**:
   - 목차가 없을 경우 대체 명칭으로 `"청크 N"` 대신 `i18n` 다국어 번역 키 (`viewer.chapter_fallback`)를 적용하여 한국어 기준 **`"1장"`, `"2장"`** (영문: `"Chapter 1"`, `"Chapter 2"`)으로 세련되게 표시하도록 변경.

2. **다국어 사전 (`static/i18n/ko.json`, `en.json`)**:
   - `"chapter_fallback": "{num}장"` (ko), `"Chapter {num}"` (en) 키 추가.

3. **백엔드 EPUB 파서 (`services/text_epub_content_service.py`)**:
   - **비표준 감지 강화**: OPF manifest 속성이 비표준이라도 `.ncx` 확장자나 `toc`, `nav` 파일명을 통한 Fallback 감지 추가.
   - **대소문자 무시 XML 파싱**: NCX XML 파싱 시 `navmap`, `navpoint`, `navlabel`, `text`, `content` 태그를 대소문자 구별 없이 유연하게 탐색.
   - **제목 보완**: 목차 제목 텍스트가 비어있을 경우 `"{num}장"` 형태의 기본값 부여.

---

## 해결 사항

- 비표준 EPUB 파일에서도 NCX / NAV 목차가 유연하게 파싱되어 정상 표시됨.
- 목차가 없는 도서에서도 `"청크 1"` 대신 **`"1장"`, `"2장"`** 형태로 가독성 높게 표시됨.
