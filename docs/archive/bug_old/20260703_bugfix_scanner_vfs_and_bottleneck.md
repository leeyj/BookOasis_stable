---
title: "스캐너 VFS 갱신 오류 및 병목 현상 개선"
project: "BookOasis"
category: "bugfix"
date: 2026-07-03
tags: [scanner, vfs, bottleneck, bugfix]
---

# 🐛 스캐너 VFS 갱신 오류 및 병목 현상 개선 (Bugfix Report)

## 📌 버그 내역 (Issue Description)
1. **대시보드 병목 (GIL 점유):** 대량의 스캔 작업(멀티스레딩) 중 Python의 GIL(Global Interpreter Lock)이 스캐너에 의해 독점되어, 사용자 대시보드(웹 서버)가 정상적으로 응답하지 못하고 멈추는 병목 현상이 발생함.
2. **정합성(데이터 유실) 문제:** 스캔 도중 예기치 않은 강제 종료나 메모리 초과 발생 시, 처리 중이던 메타데이터 정보가 DB에 반영되지 않고 유실됨.
3. **허위 에러 리포트 (70,000건 폭탄):** 원격지(rclone) 파일 스캔 중 지연 스캐너(Lazy Scanner)가 표지를 나중에 추출하도록 되어 있음에도 불구하고, 표지가 없다는 `NoCover` 에러가 무조건 누적되어 에러 로그가 폭주함.
4. **VFS(가상 파일 시스템) 갱신 누락:** `scheduler_service.py`에서 rclone API 호출 시 `"recursive": "true"` 파라미터가 누락되어 하위 폴더 갱신을 하지 못하고 즉시 반환(1초 컷)되는 문제 발생. 

## 💥 영향도 (Impact)
- 7만 권 이상의 도서 스캔 시 웹 서버 접속이 불가능해져 사용자 경험 극심한 저하.
- VFS 갱신 누락으로 인해, 실제로 변경된 내용이 즉각적으로 반영되지 않고 스캔 효율이 크게 저하됨.
- 무의미한 에러 로그 7만 건이 시스템 자원을 낭비함.

## 🛠️ 수정 사항 (Changes)
**수정된 소스 파일명:** 
- `tools/scanner/core.py`
- `services/scheduler_service.py`

**조치 상세 내역:**
1. **하이브리드 In-Memory 주기적 Flush:** `core.py`에서 100권 또는 50폴더 단위로 모아둔 데이터를 DB에 Bulk Insert & Commit(트랜잭션) 하여 유실을 완벽 방지.
2. **GIL 스로틀링 휴식 부여:** 묶음 처리가 끝날 때마다 `time.sleep(0.01~0.05초)`를 주입하여 백그라운드 스레드가 GIL을 잠시 놓아주도록 개선(대시보드 먹통 해소).
3. **허위 NoCover 방어 로직:** `core.py`에서 `is_remote`가 참일 경우 `NoCover` 에러 리스트 등재를 무시하도록 예외 처리.
4. **rclone API 재귀 탐색 보장:** `scheduler_service.py`의 API 페이로드에 `"recursive": "true"`를 명시하고, 대기 타임아웃을 `3600`초로 대폭 늘려 실제 VFS 캐싱이 완벽히 끝난 후 스캔이 돌도록 수정.

## ✅ 해결 사항 (Resolution)
- 변경이 없는 폴더 70,000건 대상 스캔이 불과 **102초(약 1분 42초)** 만에 Ultra-fast skip 처리됨.
- 스캔 중에도 대시보드 뷰어와 관리자 페이지 모두 정상 접속 및 동작 확인.
- rclone VFS 사전 갱신(약 3분 소요) 대기를 통해 100% 캐싱 완료 보장.
