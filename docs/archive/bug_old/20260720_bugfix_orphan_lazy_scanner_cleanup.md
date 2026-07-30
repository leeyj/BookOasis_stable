---
id: "20260720_bugfix_orphan_lazy_scanner_cleanup"
date: 2026-07-20
category: "bugfix"
severity: "high"
status: "fixed"
tags: [manage, shell, subprocess, popen, signal, forwarding, lazy-scanner, orphan, parent-worker, cleanup]
---

# 20260720 — 고아 레이지 스캐너 강제 정리 및 시그널 전파(Signal Bridge) 보완 완료

## 버그 내역

### 현상
- 메인 스캐너 워커(`scanner_worker.py`)를 재구동하거나 정지할 때, 자식 서브프로세스로 기동 중이던 `lazy_scanner.py` 가 부모의 정지 후에도 고아 프로세스(Orphan Process) 상태로 살아남아 DB에 지속적인 쓰기 락을 쥐고 작동함.
- 이로 인해 다음 업데이트/재시작 루틴에서 DB 복구기(`db_recovery.py`)가 가동될 때 복구 프로세스가 OOM으로 강제 킬(`Killed`)되거나 업데이트 재기동이 완전 실패하는 장애 발생.

### 근본 원인
1. **자식 격리성**: 부모 워커가 `subprocess.run` (동기식 대기) 중 `SIGTERM`을 받더라도 자식 프로세스의 메모리 구조와는 격리되어 있어 `stop_requested` 전역 플래그가 전파되지 않음.
2. **소탕 결여**: `manage.sh stop` 구문에서 Gunicorn 웹 서버와 스캐너 워커 프로세스만 정리할 뿐, 독자적인 서브프로세스인 `lazy_scanner.py` 를 능동적으로 검출 및 사살하는 클린업 코드가 부재했음.

## 영향도
- 대규모 만화책 보관함에서 레이지 스캔 진행 중 업데이트가 가동될 시 백그라운드 DB 충돌이 상시 유발되며, 부팅 시 복구 오동작으로 인한 시스템 기동 불능 결함 초래.

## 수정 사항

### 수정 파일 목록

#### `manage.sh`
- `stop` 및 프로세스 클린업 분기 하단에 **독립 레이지 스캐너 소탕 루틴** 장착.
- `pgrep -f "tools/lazy_scanner.py"` 및 `find_pids_by_pattern` 기반으로 백그라운드의 고아 레이지 스캐너를 식별하여 `SIGTERM` (30초 대기 유예) 전송 및 미종료 시 `SIGKILL (kill -9)`을 날려 정리하도록 보완.

#### `services/scanner_queue.py`
- 전역 변수 `active_subprocess = None` 추가.
- `_process_lazy_scan()` 내부의 동기식 `subprocess.run` 을 자식 프로세스 생명주기 제어가 가능한 **`subprocess.Popen`** 구동 방식으로 개편.
- 현재 실행 중인 서브프로세스 핸들을 `active_subprocess` 에 저장하고, 완료 및 해제 시점 관리 구현.

#### `utils/signal_helper.py`
- 종료 시그널 감지 리스너(`handle_signal`) 내에 **자식 프로세스 시그널 연동 브릿지(Signal Bridge)** 추가.
- 부모 워커가 종료 신호를 감지하는 즉시 `services.scanner_queue.active_subprocess` 가 존재하는지 검사하여, 존재할 경우 자식에게 `.terminate()` (SIGTERM) 신호를 다이렉트로 전파하도록 설계.

## 해결 사항
- 부모 워커가 중지되는 즉시 자식 레이지 스캐너도 시그널 브릿지를 타고 우아하게 함께 종료되며, 혹시 모를 고아 프로세스가 존재하더라도 `manage.sh stop` 단계에서 100% 포착하여 완벽히 정리하고 기동하도록 보강하여 배포 안정성을 궁극으로 달성했습니다.
