---
title: "YAML 파서 리스트 항목 변형 오류 및 불필요한 Regex Fallback 트리거 교정"
category: "bugfix"
date: 2026-07-22
severity: "medium"
affected_files:
  - "tools/scanner/metadata/kavita_yaml.py"
  - "tools/scanner/parser.py"
tags: [yaml, parser, kavita, regex_fallback, fix]
---

# YAML 파서 리스트 항목 변형 오류 및 불필요한 Regex Fallback 트리거 교정

## 1. 결함 원인 분석
- `kavita.yaml` 메타데이터 파싱 시, 기존 `_normalize_dash_prefixed_mapping_lines` 정규식이 PyYAML 로딩 전에 먼저 실행되어 정상적인 YAML 대시 리스트(`tags:`, `genres:` 아래의 `- 항목: 내용` 등) 요소의 콜론(`:`)까지 루트 매핑 구조로 무분별하게 강제 변경시켰습니다.
- 이로 인해 표준 YAML 구문 규칙이 깨져 `mapping values are not allowed in this context` 오류가 발생하고, 매번 Regex Fallback Parser가 가동되던 현상이 파악되었습니다.

## 2. 주요 수정 사항
- **[tools/scanner/metadata/kavita_yaml.py](file:///c:/project/media_server/tools/scanner/metadata/kavita_yaml.py)** 및 **[tools/scanner/parser.py](file:///c:/project/media_server/tools/scanner/parser.py)**
  1. **원본 파싱 선시도 (1차)**: 보정 정규식을 거치지 않은 순수 원본 `raw_content`를 표준 `yaml.load()`로 1차 시도하여, 표준 리스트 구조(- 항목) 메타데이터가 손상 없이 바로 정밀 파싱되도록 교정.
  2. **루트 대시 오탈자 보정 조건 강화 (2차)**: 1차 파싱이 실패한 오탈자 메타파일에 한해서만 보정 정규식을 적용하되, 들여쓰기가 거의 없거나(0~2칸) 알려진 루트 매핑 키(`KNOWN_KAVITA_KEYS`)인 경우에만 대시(`-`)를 제거하도록 조건 정밀화.

## 3. 검증 결과
- 표준 YAML 리스트(`- 콜론:이 포함된 항목`)가 파싱 에러 없이 단 한 번에 표준 파서로 파싱되며, 불필요한 Regex Fallback 로그 출력이 사라짐을 확인.
