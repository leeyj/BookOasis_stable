---
title: "표지 이미지 WebP 일괄 변환 및 스캐너 WebP 전환"
project: "BookOasis"
category: "bug"
date: 2026-06-22
tags: [covers, webp, migration, scanner, optimization]
---

# 🐛 표지 이미지 WebP 일괄 변환 및 스캐너 WebP 전환

## 1. 버그/개선 내역
- **현상**: 보관함 및 대시보드 화면 진입 시, 동시 다발적으로 요청되는 표지(Cover) 이미지들의 용량(수백 KB ~ 1MB 이상)으로 인해 외부 인터넷망 및 클라우드플레어 접속 환경에서 현저한 로딩 딜레이가 발생함.
- **원인**: 스캐너가 추출하여 저장하는 표지 파일 확장자가 `.jpg` 및 `.png`로 고정되어 있고, 압축률 최적화 없이 저장되므로 대량 서빙 시 대역폭 및 I/O 과부하를 초래함.

## 2. 영향 범위
- 표지 이미지 마이그레이션 스크립트 (`tools/convert_covers_to_webp.py`)
- 스캐너 표지 추출 모듈 (`tools/scanner/cover.py`)
- 시스템 데이터베이스 (`db/media_general.db`, `db/media_adult.db`)

## 3. 수정 사항
- **변환 스크립트 제작** (`tools/convert_covers_to_webp.py`):
  - 로컬 디스크 상의 기존 표지 이미지들을 `Pillow` 라이브러리를 통해 WebP 포맷으로 일괄 인코딩 변환 후, 이전 파일들을 안전하게 삭제하고 DB의 `cover_image` 필드값도 `.webp`명으로 갱신하는 일회성 툴을 구축함.
- **스캐너 모듈 수정** (`tools/scanner/cover.py`):
  - `Pillow` 이미지 객체 인코딩 로직을 탑재하여 표지 추출 시 `.webp` 확장자 파일로 저장하도록 전환함.
  - Base64 커버 복원, 1:1 매핑 복사, EPUB 표지 직접 추출, ZIP 첫 페이지 추출 시 모두 `Pillow`를 통해 강제 WebP 포맷 인코딩 저장을 적용함.

## 4. 해결 사항
- 보관함 진입 시 다운로드 받아야 하는 표지 이미지들의 총 트래픽 용량을 약 60~80% 절감함으로써 로딩 반응 속도를 극대화함.
- DB 기반 파일 매핑 아키텍처를 해치지 않고 파일 확장자만 `.webp`로 변환하여 저장 및 렌더링되므로, 기존 구형 파일들과의 하이브리드 서빙 호환성을 유지함.
