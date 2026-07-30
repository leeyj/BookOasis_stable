---
title: "VFS 캐시 새로고침 API 호출 타임아웃 20분(1200초) 유지 및 의사결정"
project: "BookOasis"
category: "improvement"
date: 2026-07-06
tags: [improvement, scanner, scheduler, vfs, timeout, rollback]
---

# 🚀 VFS 캐시 새로고침 API 호출 타임아웃 20분(1200초) 유지 및 의사결정 보고서

## 1. 개선 및 의사결정 내역 (Decision Report)
- **배경**: 원격 드라이브(VFS)에 수만 권 이상의 도서가 적재되어 있는 대규모 환경에서는 `/vfs/refresh` API 갱신에 오랜 시간이 걸려 60초 등 짧은 타임아웃 적용 시 스캔 대상이 정상적으로 확보되지 못하고 도중 실패하는 부작용이 발견되었습니다.
- **조치 사항**:
  - VFS 캐시 새로고침 API 호출(`urllib.request.urlopen`) 시의 타임아웃 값을 기존 최적 사양인 **`1200`초(20분)**로 원복하여 갱신 과정을 온전히 대기하도록 롤백했습니다.
  - 이로 인해 발생하는 Gunicorn 워커의 타임아웃 종료 이슈는, 먼저 구축 완료한 **자동 이어하기(Auto-Resume)** 기능이 서버 재기동 시점에 중단되었던 지점부터 지능적으로 스캔을 재개해주므로 안정성이 충분히 상쇄 및 보강됩니다.

## 2. 영향도 (Impact Assessment)
- **영향 범위**: 스캔 실행 전 VFS 동기화 라이프사이클 및 타임아웃 한계
- **효과**: 대규모 도서 관리 환경의 원격 VFS 탐색 누수 현상을 예방하고, 만에 하나 타임아웃으로 워커가 재기동되더라도 처음부터 다시 스캔하는 낭비 없이 안정적으로 마저 이어서 작업을 완수할 수 있습니다.

## 3. 수정 사항 및 해결 사항 (Resolutions)
- **수정 소스 파일**: 
  - [scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py)
    - `run_scan_job` 내 `urllib.request.urlopen` 호출 부분의 `timeout` 파라미터 값을 `1200`으로 롤백 복구.

---
*최종 작성일: 2026-07-06*
