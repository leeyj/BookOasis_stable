---
title: Task - docker_sigterm_trap
project: BookOasis
category: history
date: 2026-07-19
type: task
---
- [x] manage.sh 종료 로직(Graceful Shutdown) 개선 및 스캔 체크 가드 추가
- [x] entrypoint.sh에 SIGTERM/SIGINT 트랩 및 하위 프로세스 전파 로직 구현
- [x] Dockerfile 및 entrypoint 실행 연동 확인
- [x] 수동 빌드 및 종료 시그널 전파 테스트 검증
- [x] 문서 수집 및 업데이트
- [x] tools/scanner/engine.py 들여쓰기 구문 오류(IndentationError) 조치 완료
- [x] 미검출 커버 fallback SVG 라벨 오표기(TEXT) 버그 조치 완료
- [x] 원격 서버 Database Malformed 손상 복구 완료
