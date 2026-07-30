# 잘못된 YAML 파일 경로 리포트 기록 개선

## 증상

- `kavita.yaml` 문법 오류가 있으면 로그에는 YAML 파싱 에러가 남지만, 어떤 파일 경로에서 발생했는지 스캔 리포트에서는 확인하기 어려웠습니다.

## 조치

- `tools/scanner/metadata/kavita_yaml.py`에서 YAML 파싱 실패 시 구조화된 `parser_warnings` 항목을 생성하도록 수정했습니다.
- `tools/scanner/metadata/__init__.py`에서 이 경고 목록을 메타데이터 병합 결과로 보존하도록 확장했습니다.
- `tools/scanner/tasks.py`에서 해당 경고를 `YamlParseError` 형식으로 스캔 에러 리포트 목록에 포함하도록 연결했습니다.

## 결과

- 스캔은 계속 진행됩니다.
- 잘못된 `kavita.yaml`은 리포트에 파일 경로와 함께 기록됩니다.

## 영향 파일

- tools/scanner/metadata/kavita_yaml.py
- tools/scanner/metadata/__init__.py
- tools/scanner/tasks.py