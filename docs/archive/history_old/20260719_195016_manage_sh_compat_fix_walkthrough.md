---
title: Walkthrough - manage_sh_compat_fix
project: BookOasis
category: history
date: 2026-07-19
type: walkthrough
---
# sh ./manage.sh 기동 오류 버그 조치 결과 (Walkthrough)

도커 사용자가 `docker exec -it bookoasis sh ./manage.sh` 형태로 명시적 `sh` 인터프리터 기동 시, bash 전용 환경변수가 지원되지 않아 작업 디렉토리가 소실되던 오류를 완벽하게 조치하였습니다.

## 변경 사항 (Changes Made)

### [Server Controls]

#### [MODIFY] [manage.sh](file:///c:/project/media_server/manage.sh)
- `SCRIPT_PATH` 및 `Fallback` 구문 보강:
  - `BASH_SOURCE` 변수가 제공되지 않는 일반 POSIX sh 및 도커 CLI 진입 환경에서, 스크립트 실행 매개변수 `$0`을 사용해 상대/절대 주소에서 물리 `dirname`을 정상 복원하도록 개선.

---

## 검증 결과 (Verification Results)

### 호환성 검증
- 수정 후 `sh ./manage.sh status` 및 `bash ./manage.sh status` 모두에서 예외 없이 정확한 절대 경로(/app 또는 media_server)를 타겟팅하여 작동 및 실행됨을 검증 완료하였습니다.
