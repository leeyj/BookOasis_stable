---
title: Walkthrough - aladin_plugin_logging
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 워크쓰루: 알라딘 플러그인 API 호출 상세 디버그 로깅 추가

알라딘 OpenAPI 검색 시 검색 결과가 누락되거나 오류가 나는 원인을 진단할 수 있도록 TTBKey 조회 과정, 요청 주소(TTBKey 마스킹), 응답 바디 원문, 예외 발생 시 상세 스택 트레이스를 콘솔 출력(`print`)하는 로그를 보강하였습니다.

## 변경 내용

### 1. 플러그인 상세 로깅 주입

#### [MODIFY] [aladin.py](file:///c:/project/media_server/plugins/metadata/aladin.py)
- `_get_ttbkey` 내 DB 조회 및 `.env` 파일 로드 흐름에 상세 진행 로그를 출력하도록 수정하였습니다. (키 마스킹 기법 적용)
- `search` 함수 내 요청할 API 엔드포인트 URL 및 파라미터 로깅, `urllib` 응답 결과 Status와 RAW 바디(JSON 원문) 로깅, API 에러 응답 수신 시의 메시지 로깅, 예외 캐치 시 `traceback.format_exc()`를 통한 디테일한 에러 상세를 남기도록 개선하였습니다.

## 검증 결과

- 로컬 변경 내역 검증 후, 배포 스크립트 `python deploy.py`를 실행하여 원격 홈 서버(`192.168.0.20`) 배포를 완료하였습니다.
- 메타데이터 검색 창에서 알라딘 도서 검색 시도를 한 뒤 서버 콘솔 로그를 모니터링하여 로그 출력 형식이 완비되었음을 확인합니다.
