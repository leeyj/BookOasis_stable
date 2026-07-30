---
title: Task - representative_cover_image_mismatch_fix
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 대표 표지 이미지 불일치 해결 작업 목록

- [x] `services/book_service.py` 내 SQL 쿼리 대표 표지 조회 로직 수정
  - [x] 4개 분기 쿼리의 `MAX(cover_image)`를 첫 권(오름차순 기준) 표지 반환 서브쿼리로 변경
- [x] 로컬 구문 컴파일 테스트 및 배포
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재구동
- [x] 버그 수정 이력 문서화 및 전역 동기화
  - [x] `docs/bug/20260620_bugfix_representative_cover_image_mismatch.md` 작성
  - [x] `docs/workflow.md` 이력 추가
  - [x] `walkthrough.md` 완료 문서 작성
  - [x] `tools/collect_docs.py` 실행
