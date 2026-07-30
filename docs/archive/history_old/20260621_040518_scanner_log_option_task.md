---
title: Task - scanner_log_option
project: BookOasis
category: history
date: 2026-06-21
type: task
---
# 작업 목록 (task.md)

- [x] 데이터베이스 기본 설정 마이그레이션 적용
  - [x] `database.py` 수정 (`default_settings`에 `SCANNER_WRITE_LOG` 키 추가)
- [x] 환경설정 일반 설정 UI 및 스크립트 연동
  - [x] `tab_media_library.html` 일반설정 폼에 셀렉트 박스 추가
  - [x] `settings_tab.js` 로딩/저장 통신 로직 업데이트
- [x] 스캐너 로그 무력화 가로채기(builtins.print) 비동기 반영
  - [x] `tools/scanner/core.py`에 DB 설정 판별 헬퍼 구현 및 print 모킹 적용
- [x] 로컬 기능 검증 및 문서 정리
  - [x] 로컬 환경에서 로그 옵션 ON/OFF에 따른 동작 테스트
  - [x] walkthrough.md 작성 및 이력 갱신
  - [x] (경고) 원격 배포 프로세스는 제외하고 로컬 작업만 마감
