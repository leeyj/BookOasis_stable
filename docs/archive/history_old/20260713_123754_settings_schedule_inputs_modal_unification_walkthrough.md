---
title: Walkthrough - settings_schedule_inputs_modal_unification
project: BookOasis
category: history
date: 2026-07-13
type: walkthrough
---
# 스캐너 다중 권수 등록 오류 조치 워크쓰루

이미지 디렉토리 가상 책(`__folder__.imgdir`) 스캔 시 발생하던 다중 권수 누락 문제를 해결하기 위해 아래 작업을 수행했습니다.

## 🛠️ 수정 사항
1. **[tasks.py](file:///c:/project/media_server/tools/scanner/tasks.py)**:
   - `process_folder_task` 의 진입 시점에 `root` 경로 문자열에서 백슬래시(`\`)를 슬래시(`/`)로 일괄 치환하여 윈도우 환경에서도 정규화된 경로 구분자를 사용하도록 보장했습니다.
2. **[engine.py](file:///c:/project/media_server/tools/scanner/engine.py)**:
   - `_scan_library_internal` 에서 `os.walk` 루프 진입 시 `root` 경로를 마찬가지로 `/` 로 정규화하여 탐색 단계의 모든 파일 경로가 일관된 정형을 갖추도록 처리했습니다.
   - `process_batch` 에서 DB의 UNIQUE 제약조건 필드인 `file_path`에 신규 삽입하거나 수정할 때, 강제로 `.replace('\\', '/')`를 적용하여 슬래시와 백슬래시가 혼용된 이상 경로가 인서트되는 원인을 근절하였습니다.

## 🧪 E2E 최종 검증 결과
- 모든 경로 포맷이 슬래시 스타일 `/` 로 안전하게 통일되었습니다.
- 이에 따라 중복 검사 오동작, 소프트 딜리트 미복구 버그가 해결되어 여러 개의 권수 폴더가 누락 없이 올바르게 모두 서재로 스캔 등록되는 것을 확인했습니다.
