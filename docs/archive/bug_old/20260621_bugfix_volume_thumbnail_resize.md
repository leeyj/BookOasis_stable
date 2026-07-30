---
title: "도서 상세 목록 단행본 썸네일 크기 조정 및 설명글 스크롤 제거 개선"
project: "BookOasis"
category: "improvement"
date: 2026-06-21
tags: [improvement, css, javascript, frontend, thumbnail, scroll]
---

# 🎨 도서 상세 목록 단행본 썸네일 크기 조정 및 설명글 스크롤 제거 개선

## 1. 개선 내역 및 요청 사항
- **요청 사항**:
  1. 단행본 목록 리스트의 썸네일 크기를 대폭(세로 240px) 키워서 표지 시인성을 직관적으로 극대화.
  2. 제목과 파일 경로가 한 줄에 뭉쳐지는 현상을 해결하기 위해 파일 경로명을 아랫줄로 내림.
  3. 도서 상세 설명글 영역에 생기는 세로 스크롤바를 없애고 동적으로 아래로 늘어나도록 처리.

## 2. 영향도
- **영향 범위**:
  - 도서 상세 목록 리스트 뷰 (`.volume-card` 내 `.volume-thumb` 클래스 및 파일명 줄바꿈)
  - 도서 상세 헤더 패널 (`.book-summary-text` 클래스 적용 범위)
- **우선순위**: 보통 (사용성 개선)

## 3. 변경 상세 내용
- **수정 소스 파일**:
  - `static/css/style.css`
  - `static/js/modal.js`
- **조치 내용**:
  1. **썸네일 크기 수정**: `.volume-thumb` 클래스의 기존 크기(`52px * 72px`)를 세로 240px 기준으로 확대한 `174px * 240px`로 수정하였습니다.
  2. **파일명 줄바꿈**: `static/js/modal.js` 내 단행본 카드 렌더링 코드에서 `b.file_path`의 `span` 요소를 `volume-title-row` 외부로 분리하고 `display: block;` 속성을 부여하여 제목 아랫줄에 정렬되도록 조정하였습니다.
  3. **스크롤 제거**: `.book-summary-text` 클래스에서 `max-height: 100px;` 및 `overflow-y: auto;` 제한을 삭제하여 텍스트 길이에 따라 높이가 동적으로 아래로 늘어나도록 개선하였습니다.

## 4. 해결 사항 및 검증 결과
- 수정 후 `deploy.py`를 통해 원격 배포 및 재구동을 진행하였고, 사용자가 직접 E2E 기능/레이아웃 검증을 수행하기로 확인하였습니다.
