---
title: Task - metadata_apply_detail_stay
project: BookOasis
category: history
date: 2026-06-21
type: task
---
# 작업 목록 (TODO List)

- [x] `metadata_search.js` 내 메타데이터 적용 완료 후 뷰 판별 및 갱신 로직 수정
  - [x] `isSeriesMode === true` 일 때 `window.openBookDetail`을 호출하도록 글로벌 네임스페이스 명시화
  - [x] `isSeriesMode === false` 일 때 `history.state`를 판별하여 상세 보기 화면 새로고침 연동
- [x] 서버 배포 및 변경사항 원격 반영 (`deploy.py` 실행)
- [x] 버그 수정 이력 문서 작성 (`docs/bug` 폴더 내에 YYYYMMDD_bugfix 문서 작성)
- [/] E2E 교차 검증 및 기능 테스트
