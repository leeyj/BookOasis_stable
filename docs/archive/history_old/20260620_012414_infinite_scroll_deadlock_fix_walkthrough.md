---
title: Walkthrough - infinite_scroll_deadlock_fix
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 무한 스크롤 중복 락 해제 결과 (Walkthrough)

무한 스크롤 트리거 시 락이 비정상적으로 유지되어 추가 페이지 로딩이 중단되던 중복 락(데드락) 문제를 해결하였습니다.

## 변경 사항 요약 (Changes)

### 프론트엔드 라이브러리 코어

#### [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
- 스크롤 리스너가 조건 충족 시 동기적으로 락을 잡던 `state.isLoading = true;` 구문을 제거하였습니다.
- 실제 책 목록을 로딩하는 `loadBooksList` 내부 초입에 있는 락 검사 기능과 충돌이 발생해 API 로딩이 통째로 묵살되던 기작을 정상화하였고, 진단 완료된 임시 디버깅용 `console.log`들을 정리했습니다.

## 검증 결과 (Verification Results)
- 소스 코드 수정 후 `deploy.py`를 실행하여 원격 홈 서버에 배포하고 데몬을 정상 재구동시켰습니다.
- F12 브라우저 콘솔에서 더이상 중복 락에 갇혀 `isLoading: true`로 응답이 멈추는 오작동이 없으며, 마우스 휠을 통해 하단으로 스크롤 시마다 비동기로 다음 페이지 도서 목록을 유연하게 계속 호출해 냄을 검증 완료했습니다.
