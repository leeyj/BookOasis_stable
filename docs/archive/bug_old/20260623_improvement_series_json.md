---
title: "스캐너 엔진 series.json 메타데이터 파싱 지원 추가"
project: "BookOasis"
category: "improvement"
date: 2026-06-23
tags: [scanner, metadata, series.json, webtoon]
---
# 개선 내역
웹툰 등 일부 만화 폴더의 경우 저자, 설명 등의 메타데이터가 `kavita.yaml`이나 `info.xml`이 아닌 `series.json` 파일에 저장되어 있는 경우가 발견됨. 기존 스캐너 엔진은 해당 파일을 스캔 대상에서 제외하고 있었기 때문에 작품의 정보(저자, 설명 등)가 누락되어 노출되지 않는 문제가 있었음.

# 해결 사항
1. **파서 추가 (`tools/scanner/parser.py`)**
   - `series.json` 구조(JSON)를 파싱하여 `author`와 `desc`(설명) 값을 추출하는 `parse_series_json` 함수를 구현함.
2. **스캐너 코어 연동 (`tools/scanner/core.py`)**
   - 개별 시리즈 폴더를 스캔할 때, 기존의 YAML, XML 파서와 함께 JSON 파서도 연달아 실행하도록 추가함.
   - 3가지 파일 포맷 중 어느 곳에라도 메타데이터가 존재할 경우 상호 보완적으로 병합(Merge)하여 빈 값을 채워넣도록 `merged_meta` 로직을 고도화함.

# 결과
이제 `series.json`만 존재하는 웹툰/만화 폴더들도 정상적으로 저자명 및 작품 설명이 파싱되어 웹 뷰어에서 풍부한 정보를 제공할 수 있게 됨.
