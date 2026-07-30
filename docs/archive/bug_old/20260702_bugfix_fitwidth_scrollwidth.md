---
title: "오버레이 fit-width 버그 수정 및 웹툰 너비 조절 기능 추가"
project: "BookOasis"
category: "bugfix"
date: 2026-07-02
tags: [bugfix, viewer, css, comic, webtoon, fit-width]
severity: medium
status: resolved
---

# 버그 수정 내역: fit-width CSS 특이성 충돌 및 웹툰 너비 조절 기능 추가

## 버그 내역

### 증상
- `너비맞춤` 버튼을 눌러도 만화 페이지가 화면 너비에 맞춰지지 않고 `높이맞춤` 모드처럼 보임
- 특히 단일 페이지(`1장보기`) 뷰에서도 동일 현상 발생

### 근본 원인
`tab_media_library_viewer.css` 에서 페이지 쌍(`.comic-page-pair img`) 공통 규칙이
`fit-height`와 `fit-width`를 **동일한 선택자**로 묶어 `width: auto`를 적용함으로써,
`fit-width img { width: 100% }` 보다 더 구체적인 선택자가 이를 덮어쓰는
**CSS 특이성(specificity) 충돌** 발생.

## 영향도
- 만화책 뷰어 전체 (`fit-width` 모드)
- 특히 1장 보기 + 너비맞춤 조합에서 완전히 동작하지 않음

## 수정 파일
- `static/css/tab_media_library_viewer.css`
- `static/js/viewer/reader_settings.js`
- `static/js/viewer/renderer.js`
- `static/js/viewer/navigation.js`
- `static/js/viewer_comic.js`
- `static/js/viewer.js`
- `templates/components/media_viewer.html`
- `static/i18n/ko.json`, `static/i18n/en.json`

## 해결 사항
- `너비맞춤` 모드에서 페이지 이미지가 실제 화면 너비에 맞춰 출력됨
- `1장 + 너비맞춤` 조합에서 `width: 100%` 정상 적용
- 스크롤 모드(웹툰) 에서 이미지 표시 너비를 600~900px 범위에서 50px 단위로 조절 가능
- 설정 값이 localStorage에 저장되어 다음 뷰어 열기 시 자동 복원
