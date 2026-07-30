---
title: Walkthrough - metadata_apply_detail_stay
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 워크쓰루: 도서 메타데이터 적용 후 상세화면 이탈(리스트 튕김) 조치

도서 상세 보기 화면에서 개별 권수(단행본)의 메타데이터를 검색하여 적용했을 때, 카테고리 목록으로 화면이 튕기는 현상을 수정하고 제자리에서 상세 정보가 갱신되도록 개선 완료하였습니다.

## 변경 내용

### 프론트엔드 모듈 뷰 리팩토링
- **[MODIFY] [metadata_search.js](file:///c:/project/media_server/static/js/metadata_search.js)**:
  - `selectMetadataBook` 함수 내에서 `isSeriesMode === false`인 분기일 때 무조건 `window.selectCategory`를 호출하던 동작을 변경했습니다.
  - 브라우저 히스토리 상태(`history.state`)를 점검하여 현재 사용자가 상세 보기 화면에 머물러 있는지 여부(`history.state.view === 'detail'`)를 탐지합니다.
  - 상세 보기 뷰가 활성화되어 있다면, 현재 보고 있던 시리즈 명칭(`history.state.series`)을 활용해 `window.openBookDetail(null, activeSeries)`을 호출함으로써 도서 목록으로 돌아가지 않고 상세 정보만 새로고침되도록 해결했습니다.
  - 상세 보기 상태가 아닐 때(예: 일반 그리드 목록에서 우클릭 메뉴로 검색/적용한 때)만 기존과 동일하게 카테고리 새로고침(`window.selectCategory`)을 실행하도록 처리했습니다.
  - `isSeriesMode === true` 분기에서도 `openBookDetail` 함수를 호출할 때 글로벌 네임스페이스인 `window.openBookDetail`을 활용하도록 명시하여 strict mode 등에서의 잠재적인 `ReferenceError`를 완전히 해소했습니다.

## E2E 및 수동 검증 결과
1. **서버 배포 및 재시작**:
   - `python deploy.py`를 실행하여 수정된 `metadata_search.js` 코드를 원격 홈 서버(`192.168.0.20`)로 무사히 전송하고, 단독 재기동 프로세스를 정상 완료하였습니다.
2. **수동 검증 시나리오 완수**:
   - 도서 상세 화면 진입 ➔ 특정 권수 우클릭 ➔ "메타정보 검색" ➔ 1권 등 메타데이터 정보 선택 ➔ 적용 완료 확인.
   - 모달창만 자연스럽게 닫히며 도서 목록으로 튕겨나가지 않고, 도서 상세 보기 화면 내의 정보와 썸네일 표지가 실시간으로 부드럽게 부분 갱신되는 것을 최종 확인했습니다.
