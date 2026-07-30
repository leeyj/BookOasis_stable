---
title: "Lazy 표지 스캐너 로그 기록 및 실행로그 설정 연동"
project: "BookOasis"
category: "bugfix"
date: 2026-06-22
tags: [lazy-scanner, logging, settings]
---

# Lazy 표지 스캐너 로그 기록 및 실행로그 설정 연동

## 1. 개선 내역
- Lazy 스캐너(`tools/lazy_scanner.py`) 구동 시 진행 과정에 대한 로그가 파일이나 화면에 남지 않아 기동 및 진행 상황을 알 수 없던 문제를 조치했습니다.
- 스크립트 실행 시 `media_general.db`에서 일반 설정의 `SCANNER_WRITE_LOG` 값을 동적으로 읽어 로그 출력 여부를 판별하도록 하였습니다.
- `SCANNER_WRITE_LOG`가 활성화(`'1'`)된 경우, `builtins.print`를 가로채어 프로젝트 루트의 `media_server.log` 파일에 타임스탬프와 함께 진행 상황을 실시간 덧붙여 기록하도록 조치했습니다.
- `SCANNER_WRITE_LOG`가 비활성화(`'0'`)된 경우, `builtins.print`를 빈 람다 함수로 오버라이드하여 로그가 남지 않도록 하여 불필요한 I/O 부하와 파일 크기 증가를 원천 차단했습니다.

## 2. 영향도
- **영향 범위**: Lazy 스캐너 모듈 (`tools/lazy_scanner.py`)
- **개선 효과**: 백그라운드 크론 작업이나 관리자의 [지금 실행] 수동 실행 시, 실제 Lazy 스캐너 프로세스가 정상 구동 중인지와 현재 어떤 책의 표지를 추출하고 있는지 `media_server.log` 파일의 타임스탬프 기반 실시간 스트리밍 로그를 통해 직관적으로 확인할 수 있습니다.

## 3. 수정 사항
- **수정 소스 파일**:
  - [tools/lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py): `setup_lazy_scanner_logging()` 구현 및 구동 시 호출하도록 래핑 적용

## 4. 해결 사항
- 이제 Lazy 스캐너의 실시간 진행 현황 파악이 가능하며, 사용자 설정에 따른 완전한 무손실 로그 제어가 가능합니다.
