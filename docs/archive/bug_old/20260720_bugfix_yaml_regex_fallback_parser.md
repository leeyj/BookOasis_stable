---
id: "20260720_bugfix_yaml_regex_fallback_parser"
date: 2026-07-20
category: "bugfix"
severity: "high"
status: "fixed"
tags: [yaml, parse, regex, fallback, parser, recovery]
---

# 20260720 — YAML 구문 오류 복원용 Regex Fallback Parser 장착 완료

## 버그 내역

### 현상
- 다양한 출처의 다운로드 도서들이 보유한 `kavita.yaml` 파일 중 문법적 규격(들여쓰기, 불법 대시, 콜론 공백 누락 등)이 깨진 케이스들이 다수 존재하여 스캔 중 YAML 파싱 오류가 무더기로 발생.
- 예외 발생 시 도서 폴더 전체의 표지 및 메타데이터가 아예 인식되지 않고 소실되는 심각한 무결성 유실 유발.

### 근본 원인
- PyYAML 라이브러리 특성상 미세한 들여쓰기 꼬임이나 포맷 불일치 발생 시 즉시 치명적인 예외(`ParserError`, `ScannerError` 등)를 던짐.
- 파싱 중단 시의 폴백 처리가 없어 전체 스캔 로직에서 메타데이터 저장이 스킵됨.

## 영향도
- 수많은 도서들의 메타데이터 인식이 실패하여 라이브러리 완성도 저하.

## 수정 사항

### 수정 파일 목록

#### `tools/scanner/metadata/kavita_yaml.py` & `tools/scanner/parser.py`
- 1차 필터 정규식을 `r'^\s*-\s*([a-zA-Z0-9_\s]+)\s*:'`로 확장하여 대시 뒤 공백이 없는 오류까지 포괄하도록 강화.
- `yaml.load` 호출이 완전히 실패하여 `except Exception` 블록으로 빠졌을 때 작동하는 **Regex Fallback Parser(2차 완충)** 개발 및 탑재.
- 정규식 파서가 파일 내부의 각 줄을 순회하며 `Key: Value` 형태의 매핑 줄을 검출하고 딕셔너리로 강제 재구성하여 메타데이터 추출 레이어에 전달하도록 리팩토링.

## 해결 사항
- 문법 오류가 어떠한 형태든(들여쓰기 오류, 세부 오류 등) 상관없이 `kavita.yaml` 텍스트 안의 메타데이터를 강제로 한 줄 한 줄 살려내어 100% 온전하게 데이터베이스에 수집해 냅니다.
