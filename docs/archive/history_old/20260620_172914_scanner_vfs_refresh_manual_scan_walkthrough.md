---
title: Walkthrough - scanner_vfs_refresh_manual_scan
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 수동 스캔 시 VFS 캐시 새로고침 미동작 조치 (Walkthrough)

스케줄러 이외의 CLI 실행이나 수동 트리거 시, 원격 마운트 경로(VFS) 캐시 사전 새로고침이 동작하지 않아 `os.walk` 탐색 단계에서 멈추던 버그를 최종 조치하였습니다.

## 변경 사항 요약 (Changes)

### 백엔드 스캐너

#### [MODIFY] [scanner.py](file:///c:/project/media_server/tools/scanner.py)
- **VFS 캐시 갱신 연동 내재화**: 스캔의 핵심 진입점인 `scan_library` 함수의 시작점에 `trigger_vfs_refresh`를 호출하도록 보완했습니다.
- **핀포인트 새로고침 수행**: 대상 경로가 rclone FUSE 마운트 드라이브이고 DB 설정 상 사전 갱신 옵션이 켜져 있는 경우, rclone RC API를 호출해 해당 디렉토리만 부분 갱신을 하도록 구현했습니다.

## 검증 결과 (Verification Results)
- 수정본을 원격 홈 서버에 배포 완료했습니다.
- CLI 수동 기동 테스트 결과, 대상 경로 `/home/az001a/sjva/NAS_BACKUP/books/소설` 영역만 핀포인트 새로고침이 즉시(1~2초 내) 완료되고, `물리 폴더 트리 탐색 중...` 단계가 멈춤 없이 1초도 안 되어 순식간에 통과하고 다음 라이브러리 스캔까지 매끄럽게 넘어감을 최종 확인 완료했습니다.
