---
title: "Gunicorn 기동 시 파이썬 표준 출력 실시간 보장 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, gunicorn, logging, buffer]
---

# 🐛 Gunicorn 기동 시 파이썬 표준 출력 실시간 보장 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 웹 대시보드 화면 등에서 도서관 스캔 시작 버튼을 눌렀을 때, `media_server.log` (Gunicorn의 stdout/stderr 리다이렉션 로그 파일)에 스캔 기동 관련 인쇄 메시지(`print` 문)가 실시간으로 수집되지 않고 완전히 빈 칸으로 방치되어 스캔 상황을 상시 모니터링할 수 없던 현상 발생.

## 2. 원인 분석 (Root Cause Analysis)
- 파이썬 프로세스는 출력이 터미널(TTY)이 아닌 일반 파일로 직접 리다이렉션되어 쓰일 때, 입출력 최적화를 위해 표준 출력(`sys.stdout`) 버퍼링을 강제 활성화함.
- 이로 인해 스캐너 스레드가 구동되면서 실시간으로 로그 문자열을 방출했음에도, Gunicorn이 내려앉거나 버퍼(4KB~8KB)가 가득 찰 때까지 메모리 풀 내에 출력이 갇혀 실시간 갱신이 누락되었던 것임.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [manage.sh](file:///c:/project/media_server/manage.sh)
  - Gunicorn 데몬을 백그라운드로 띄우는 기동 프로세스 라인 맨 앞에 **`env PYTHONUNBUFFERED=1`** 환경변수를 주입함.
  - 파이썬 인터프리터 수준에서 stdout/stderr 스트림 버퍼링을 원천 비활성화(Unbuffered)하여 모든 print 출력이 메모리 대기 없이 리다이렉션 타겟인 `media_server.log` 파일로 매 프레임 즉각 반영되도록 조치함.

## 4. 결과 검증 (Verification Results)
- 코드를 원격 홈 서버에 배포한 후 서비스를 재기동함.
- 웹상에서 라이브러리 스캔을 실행했을 때, `media_server.log` 파일에 실시간으로 스캔 관련 로그 및 VFS 캐시 갱신 결과 등이 지연 없이 그대로 적재됨을 최종 확인 완료함.
