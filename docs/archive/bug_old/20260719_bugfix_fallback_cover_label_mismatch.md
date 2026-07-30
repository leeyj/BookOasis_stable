---
title: "미검출 커버 fallback SVG 라벨 오표기(TEXT) 버그 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-19
tags: [cover, fallback, svg, bugfix]
---

# 🐛 미검출 커버 fallback SVG 라벨 오표기(TEXT) 버그 조치

## 1. 버그 내역
- 만화책(ZIP/CBZ)의 표지 이미지가 검출되지 않을 시, 대체 커버(fallback SVG) 이미지의 하단 포맷 텍스트 라벨이 "COMIC"이 아닌 "TEXT"로 오표기되는 버그 발생.

## 2. 영향도
- 사용자 웹 UI에서 만화책 대체 표지에 파일 포맷 종류가 잘못 매핑되어 노출됨.

## 3. 수정 사항
- 대상 파일: [stream.py](file:///c:/project/media_server/api/stream.py#L49-L62)
- 수정 내용:
  - 프론트엔드가 `/covers/fallback?format=comic`으로 요청을 넣을 때, 백엔드 `_format_cover_label` 함수에서 `'comic'` 문자열에 대해서도 `'COMIC'` 상수로 올바르게 파싱 및 반환하도록 개선. (추가적으로 `img`, `audio`에 대해서도 방어 조건으로 보완 적용)

## 4. 해결 사항
- 수정본을 운영 서버에 성공적으로 배포하였습니다.
- 배포 과정에서 감지된 운영 서버의 데이터베이스 손상(`database disk image is malformed`)에 대해서도 복구 도구(`db_recovery.py`)를 활용하여 전체 복구 및 정합성 검증을 거친 후, 미디어 서버 데몬 및 워커를 정상 기동 완료하였습니다.
