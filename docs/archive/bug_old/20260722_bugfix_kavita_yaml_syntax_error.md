---
title: "kavita_yaml.py 파이썬 문법 에러(SyntaxError) 오타 소거 조치"
category: "bugfix"
date: 2026-07-22
severity: "high"
affected_files:
  - "tools/scanner/metadata/kavita_yaml.py"
tags: [syntax_error, kavita_yaml, deploy, bugfix]
---

# kavita_yaml.py 파이썬 문법 에러(SyntaxError) 오타 소거 조치

## 1. 원인 분석
- `tools/scanner/metadata/kavita_yaml.py` 222번째 줄에 `print(...)rr:` 문법 오타가 잔존하여, 서버 시작 시 `SyntaxError: invalid syntax` 오류로 인해 원격 서버 기동이 중단되던 현상을 확인했습니다.

## 2. 조치 사항
- **[tools/scanner/metadata/kavita_yaml.py](file:///c:/project/media_server/tools/scanner/metadata/kavita_yaml.py)**
  - `print(f"[Scanner] YAML Regex Fallback also failed ({folder_path}): {fallback_err}")rr:` 뒤의 `rr:` 접미사 오타 및 중복 print 구문을 삭제하고 깔끔히 정돈했습니다.

## 3. 검증
- `python deploy.py` 실행을 통해 원격 미디어 서버가 구동 오류 없이 원활히 정상 재기동됨을 확인했습니다.
