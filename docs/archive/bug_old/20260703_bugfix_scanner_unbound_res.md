---
title: "버그 수정: 스캐너 UnboundLocalError 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-03
tags: [bug, scanner, core, fix]
---

# 🐛 버그 수정: 스캐너 UnboundLocalError 수정

## 1. 버그 내역 (Bug Description)
- Mtime 기반 광속 스킵 로직 도입 시, `core.py` 파일의 `_scan_library_internal` 내에서 변수 할당 해제 후 재참조하는 코딩 실수가 발생했습니다.
- 에러 로그: `local variable 'res' referenced before assignment`
- 루프 내에서 `del res`로 메모리를 반환한 직후에 `res.get('dir_mtime')`을 호출하려다 예외가 발생했습니다.

## 2. 영향도 (Impact)
- 정상적으로 스캔 작업이 이행되지 않고 `UnboundLocalError` 예외가 발생하여, 전체 폴더 스캔 루프에서 취소 확인(cancelling check)을 우회하게 만들었습니다.
- 그 결과, `cancelling` 상태에 빠진 채 데이터베이스 락(Lock)이 고착화되어 스캔 취소가 정상 동작하지 않았습니다.
- Mtime 캐싱 정보가 올바르게 업데이트되지 못했습니다.

## 3. 조치 사항 (Resolution)
- **수정 소스 파일**: `tools/scanner/core.py`
- 변수 `res`를 삭제(`del res`)하기 전 상단에 `dir_mtime`과 `meta_mtime`을 별도 로컬 변수로 안전하게 추출하여 할당하도록 변경했습니다.
- `cancelling` 상태 고착화를 방지하기 위해 로컬의 파이썬 스크립트를 사용하여 데이터베이스의 `scan_status`를 `ready` 상태로 직접 초기화(Reset) 조치 완료했습니다.
