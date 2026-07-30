---
title: Walkthrough - spec_scan_report_update
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 표지 이미지 라이브러리 격리 누수 조치 워크쓰루

## 변경 사항 및 해결 내용
- **단일 도서 스캔 인수 보완**: `services/book_scan_service.py` 내의 `scan_single_book` 서비스 함수에서 이미지 추출 헬퍼들을 부를 때, 조회된 `library_id` 파라미터를 넘겨주도록 코드를 보정했습니다. 이로써 `covers/{library_id}/` 격리 디렉토리에 정상적으로 표지가 수납됩니다.
- **알라딘 메타데이터 수동 매칭 격리 구현**: `plugins/metadata/aladin.py`의 `apply` 함수에서 대상 도서의 `library_id` 정보를 DB에서 추가 획득하도록 쿼리를 개선하고, 표지 파일 다운로드 및 DB 갱신 경로를 `{library_id}/book_{hash}.png` 형태로 격리 적재되도록 전면 수정했습니다.

## E2E 검증 및 특이사항
- **로컬 코드 보완 완료**: 위의 소스코드 수정을 로컬 환경에 완벽하게 반영했습니다.
- **배포 보류 (원격 스캔 상태 보존)**: 사용자의 요청에 따라 현재 원격 서버의 실시간 스캔 세션에 영향을 주지 않기 위해 **원격지 배포 및 프로세스 재구동은 진행하지 않았습니다.** 스캔 작업이 모두 마감된 시점에 `deploy.py`를 실행하여 핫픽스 코드를 반영해주시면 정상 작동합니다.
