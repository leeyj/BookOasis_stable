---
title: Task - hybrid_redis_cache
project: BookOasis
category: history
date: 2026-07-19
type: task
---
- [x] manage.sh 종료 로직(Graceful Shutdown) 개선 및 스캔 체크 가드 추가
- [x] entrypoint.sh에 SIGTERM/SIGINT 트랩 및 하위 프로세스 전파 로직 구현
- [x] Dockerfile 및 entrypoint 실행 연동 확인
- [x] 수동 빌드 및 종료 시그널 전파 테스트 검증
- [x] manage.sh start() 함수 시작 시 DB 무결성 체크 및 복구/스키마 업데이트 루틴 탑재
- [x] entrypoint.sh 기동 직전 동일한 무결성 체크 및 복구/스키마 업데이트 루틴 탑재
- [x] manage.sh 내 BASH_SOURCE $0 Fallback 경로 처리 패치
- [x] requirements.txt 에 redis 종속성 라이브러리 추가
- [x] docker-compose.yml 및 docker-compose.ghcr.yml 에 redis 컨테이너 서비스 추가 연동
- [x] utils/redis_helper.py 연결 유틸 및 Fallback 처리 구현
- [x] services/stream_service.py 내 진행률 Redis 캐싱 및 백그라운드 SQLite 동기화(Write-Behind) 구현
- [x] entrypoint.sh 및 manage.sh 종료 시 캐시 Flush 연동 추가
- [x] 캐시 정상 적용 및 벌크 동기화 E2E 구동 테스트
- [x] 문서 수집 및 업데이트
- [x] tools/scanner/engine.py 들여쓰기 구문 오류(IndentationError) 조치 완료
- [x] 미검출 커버 fallback SVG 라벨 오표기(TEXT) 버그 조치 완료
- [x] 원격 서버 Database Malformed 손상 복구 완료
