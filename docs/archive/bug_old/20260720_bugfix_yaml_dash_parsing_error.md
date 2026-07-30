---
id: "20260720_bugfix_yaml_dash_parsing_error"
date: 2026-07-20
category: "bugfix"
severity: "medium"
status: "fixed"
tags: [yaml, parser, dash, metadata, kavita]
---

# 20260720 — YAML 비정상 대시 파싱 오류 보정 완료

## 버그 내역

### 현상
- 일부 도서 폴더 내 `kavita.yaml` 파일 파싱 시, 데이터베이스 스캔 과정에서 해당 도서의 메타데이터(작가, 장르, 태그, 커버 이미지 등)가 통째로 누락되는 현상이 발생.

### 근본 원인
- YAML 파일 내용 중 `- Day: '13'` 과 같이 줄 머리에 비정상적인 대시(`-`) 및 공백 접두사가 강제로 삽입된 행이 존재.
- YAML 스펙상 딕셔너리(Map) 구조 내에 일관성 없이 단일 시퀀스 대시(`- `)가 존재하면 문법 에러(`ScannerError`, `ParserError`)가 발생함.
- 예외 포착 시 전체 파싱 결과가 소실되어 빈 메타데이터로 복구되는 결함 유발.

## 영향도
- 잘못 작성된 YAML 파일이 포함된 도서의 메타데이터를 통째로 인식하지 못해 사용자 대시보드 및 상세 목록 정보가 불완전해짐.

## 수정 사항

### 수정 파일 목록

#### `tools/scanner/metadata/kavita_yaml.py`
- `parse_kavita_yaml` 메서드 내 `yaml.load` 직전, `re.sub` 정규식을 활용하여 각 줄의 시작 부분에 잘못 기입된 `- Key:` 형태를 감지해 `Key:` 형태로 치환하는 안전 필터(전처리) 추가.

#### `tools/scanner/parser.py`
- 레거시 호환용 파서 모듈의 `parse_kavita_yaml` 메서드에도 동일한 정규식 전처리 코드를 적용하여 레거시 스캐너 구동 시의 호환성 확보.

## 해결 사항
- 문법이 어긋난 YAML 파일이라도 예외를 발생시키지 않고 매핑 구조를 온전하게 복구하여, 커버 이미지 및 전체 메타데이터를 무결하게 파싱 완료합니다.
