---
title: "kavita.yaml 파싱 시 예외 처리 보강으로 스캐너 중단 방지 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-19
tags: [bugfix, scanner, yaml]
---

# 🐛 kavita.yaml 파싱 시 예외 처리 보강으로 스캐너 중단 방지 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 특정 작품 폴더 내에 위치한 `kavita.yaml` 파일이 문법적으로 유효하지 않거나 깨져있을 때 (`ParserError: while parsing a block mapping...`) 예외가 상위 호출부로 전파되어 전체 라이브러리 스캔 루프가 도중에 정지해 버리는 현상.
- 이로 인해 해당 오류가 발생한 지점 이후의 도서 색인이 정상적으로 처리되지 않음.

## 2. 원인 분석 (Root Cause Analysis)
- `tools/scanner.py` 내 `parse_kavita_yaml` 함수에서 `yaml.load(f, Loader=SafeLoader)` 호출 시 `yaml.parser.ParserError` 예외가 발생할 수 있으나, 기존 코드가 이에 대한 상세 예외 처리는 `except Exception as e` 블록에서 잡아 로그만 찍고 상위로 전파하지는 않았으나, 실제로는 예외가 발생했을 때 `data`가 정의되지 않는 등의 문제 또는 다른 예외가 발생할 위험이 있었고, PyYAML의 파서 예외 발생 시 안전하게 빈 메타데이터 딕셔너리를 핸들링하여 조기에 빠져나가도록 구조화가 다소 약했음. 
- `data = yaml.load(...)` 줄에서 터지더라도 함수 내부 `try-except`로 잘 제어되지만, stack trace가 길게 남고, 로드된 결과가 딕셔너리가 아닌 경우(`isinstance(data, dict)` 미검증 등)에 2차 에러가 터져나오는 것을 완벽하게 방어하기 위해 검증 로직을 타이트하게 보강함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [scanner.py](file:///c:/project/media_server/tools/scanner.py#L143-L179)
- `parse_kavita_yaml` 함수 내부에서 `yaml.load`의 결과를 다루기 전에 `isinstance(data, dict)` 체크를 의무화함.
- `yaml.load` 실행 중 터지는 모든 파싱/구문 예외(`yaml.parser.ParserError` 등) 발생 시 에러 메시지만 출력하고, `traceback` 전체 출력을 생략하도록 하여 로그 가독성을 개선하고 함수가 무조건 빈 메타데이터(`meta`)를 안전하게 리턴하도록 보장함.

## 4. 결과 검증 (Verification Results)
- 로컬 변경 내역을 배포하여 `deploy.py`를 실행하고, 원격 서버에 재동기화 후 재시작하여 검증할 예정.
