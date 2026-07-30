---
title: "표지 이미지 서빙 시 MIME 타입 불일치에 따른 스크롤 렉 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, covers, mime-type, scroll-performance, streaming]
---

# 🐛 표지 이미지 서빙 시 MIME 타입 불일치에 따른 스크롤 렉 조치

## 1. 버그 내역 및 증상
- 일반도서 및 성인도서 카테고리 진입 후 마우스 휠 스크롤을 내릴 때, 화면이 부드럽지 않고 끊기며 버벅거리는 스크롤 렉(프레임 드랍) 현상이 발생했습니다.
- 유독 성인도서 카테고리나 표지 카드가 많은 특정 라이브러리에서 렉 현상이 현저히 심하게 체감되었습니다.

## 2. 원인 분석
- **MIME 타입 불일치**: 스캐너 최적화를 통해 표지 파일들이 고압축 WebP 포맷(`.webp`)으로 변환되었음에도 불구하고, `/covers/<path:filename>` 정적 파일 서빙 라우터에서 응답 Content-Type(mimetype) 헤더를 `image/png`로 고정하여 전송하고 있었습니다.
- **디코딩 오버헤드 유발**: 브라우저의 렌더링 엔진은 WebP 이미지를 PNG로 잘못 인식한 뒤 디코딩을 시도하다가 실패하여, 픽셀 셰이더 및 디코딩 연산을 중복으로 실행하게 되며 프레임 드랍 병목 현상을 초래했습니다.

## 3. 조치 사항
- **[api/stream.py](file:///c:/project/media_server/api/stream.py)**:
  - `get_cover_image` 라우터 핸들러 내 `_send_cover` 내부를 전면 수정했습니다.
  - `mimetypes.guess_type(path)` 유틸리티를 적용하여 실제 파일 확장자명에 부합하는 정확한 Content-Type(예: WebP 이미지의 경우 `image/webp`)을 파이썬 백엔드에서 헤더에 자동으로 실어 내려보내도록 정밀 패치했습니다.

## 4. 해결 확인 및 영향도
- 브라우저가 표지 리소스의 정확한 확장자를 Content-Type으로 수신하게 됨에 따라 하드웨어 가속 디코더가 올바르게 작동하여, 카드 수량이 많은 카테고리 스크롤 시에도 끊김 없이 부드럽게 화면이 밀려 내려가는 극적인 프레임 최적화 효과를 보장합니다.
