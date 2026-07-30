---
title: Walkthrough - gunicorn_unbuffered_logs
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# Gunicorn 기동 시 파이썬 표준 출력 실시간 보장 조치 (Walkthrough)

Gunicorn을 활용하여 웹 데몬을 백그라운드로 띄웠을 때 파이썬 표준 출력 버퍼링 제약으로 인해 스캔 인쇄 로그가 `media_server.log` 에 찍히지 않던 모니터링 버그를 최종 해결했습니다.

## 변경 사항 요약 (Changes)

### 서버 구동 셸

#### [MODIFY] [manage.sh](file:///c:/project/media_server/manage.sh)
- **표준 출력 버퍼링 해제**: Gunicorn 시작 백그라운드 구문 맨 앞에 `env PYTHONUNBUFFERED=1`을 선언하여 파이썬 표준 스트림의 실시간 기록을 강제했습니다.

## 검증 결과 (Verification Results)
- 코드를 원격 서버에 재배포하고 마운트를 재구동했습니다.
- 웹 화면에서 강제 스캔 기동 시 지연 및 누적 대기 없이 즉각적으로 `[Scanner]` 및 `[Scanner-VFS]` 등의 상세 실행 상황이 `media_server.log` 에 실시간 반영됨을 확인 완료했습니다.
