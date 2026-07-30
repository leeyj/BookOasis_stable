---
title: "디스크 캐시 LRU 정리 도중 임시 파일(.tmp) 오인 삭제 오류 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, cache, disk-cache, evict]
---

# 🧠 [Bugfix] 디스크 캐시 LRU 정리 도중 임시 파일(.tmp) 오인 삭제 오류 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 백그라운드로 구글 드라이브 만화책 파일을 로컬 디스크 캐시로 다중 다운로드하는 중, 디스크 용량 한도(5GB) 또는 개수 한도(10개)가 초과되어 LRU 정리 로직이 구동되는 시점
- **장애 현상**: `[Errno 2] No such file or directory: '...zip.tmp' -> '...zip'` 에러가 발생하며 다운로드가 실패하고 원본 Seek 모드 가동 상태에 고착되어 시스템 응답 대기(행)가 길어지는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 백그라운드 캐싱 기능이 완전히 마비되고, 매번 고용량 만화책을 구글 드라이브 마운트 경로로부터 직접 전체 스트리밍하게 되어 엄청난 네트워크 지연(레이턴시) 및 브라우저 먹통 현상을 동반합니다.

---

## 3. 원인 파악 (Root Cause)
- [cache.py](file:///c:/project/media_server/api/cache.py) 내 `clean_up_if_needed` 메소드는 완료 플래그인 `.done` 확장자만 검사 대상에서 제외하고, 다운로드 작업이 활발히 진행 중인 `.tmp` 임시 파일들을 검사 대상에 무방비하게 노출하였습니다.
- 이로 인해 쓰기 작업 중인 임시 파일이 캐시 한도를 넘겼다고 판정되어 정리 작업(`os.remove`)에 의해 중도 삭제되었고, 결과적으로 `os.rename` 시점에 임시 파일 소실 에러가 유발된 것입니다.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [cache.py](file:///c:/project/media_server/api/cache.py#L125-L131)
- `clean_up_if_needed` 의 디렉토리 리스트 필터 루프 내 검사 조건에 `.tmp` 확장자를 명시적으로 추가하여 스킵하도록 로직을 보강했습니다.
- 백그라운드 복사가 안전하게 완료되어 온전한 `.zip` 형태가 될 때까지는 LRU 삭제 대상 후보에서 완벽히 배제됩니다.

---

## 5. 최종 검증 (Verification)
- 소스 코드 변경 배포 후 백그라운드 복사 다중 구동 환경에서 더 이상 `.tmp` 파일이 중간에 제거되는 결함 로그(`LRU 퇴출 완료: ...tmp`)가 유실되었으며, 최종 백그라운드 복사 프로세스들이 에러 없이 모두 `백그라운드 복사 완료` 상태로 정상 마감됨을 실시간 확인하였습니다.
