---
title: Task - tab_media_library_modularization_refactoring
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 라우트 레이어 모듈화 리팩토링 작업 목록

- [x] `api/admin.py` 신규 생성 및 관리자 기능 API 이관
  - [x] 라이브러리 CUD, 스케줄 설정, 라이브러리/개별 도서 스캔 라우트 이관
- [x] `api/library.py` 내 이관된 API 제거 및 임포트 최적화
- [x] `api/__init__.py`에 신규 `admin_bp` Blueprint 등록 및 연동
- [x] 배포 및 검증
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재구동
  - [x] 기존 조회 및 이관된 관리 기능 정상 동작 여부 수동 확인
- [x] 작업 이력 문서 정리 및 전역 동기화
  - [x] `walkthrough.md` 결과 문서 작성
  - [x] `tools/collect_docs.py` 실행
