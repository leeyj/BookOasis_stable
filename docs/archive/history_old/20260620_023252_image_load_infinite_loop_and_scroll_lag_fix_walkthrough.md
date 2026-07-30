---
title: Walkthrough - image_load_infinite_loop_and_scroll_lag_fix
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 이미지 로드 에러 무한 루프 및 스크롤 끊김 수정 결과 (Walkthrough)

깨진 이미지가 포함된 카테고리를 탐색할 때 발생하는 네트워크 오버헤드와 휠 스크롤 프레임 저하 현상을 안전하게 해결하였습니다.

## 변경 사항 요약 (Changes)

### 프론트엔드 컴포넌트

#### [MODIFY] [ui.js](file:///c:/project/media_server/static/js/ui.js)
- 목록 그리드의 책 카드 이미지 태그에 `onerror="this.onerror=null; this.src='...';"` 처리를 추가하여 로딩 실패 시 로컬 대체 이미지로 자동 렌더링되게 개선했습니다.

#### [MODIFY] [modal.js](file:///c:/project/media_server/static/js/modal.js)
- 시리즈 상세 페이지의 대형 대표 썸네일(`detail-cover-sm`)과 단행본 볼륨 썸네일(`volume-thumb`)의 `onerror` 핸들러 시작부에 `this.onerror=null;`을 삽입하였습니다.
- 이로써 대체 이미지 호출 실패 시 브라우저가 빠지던 무한 재귀 요청 루프를 완벽히 통제하여 CPU 스레드 점유율과 휠 스크롤 끊김 문제를 조치했습니다.

## 검증 결과 (Verification Results)
- `deploy.py`를 실행하여 최종 소스 및 아카이브된 문서를 홈 서버에 배포 완료했습니다.
- 이미지 404가 빈번한 카테고리 진입 시에도 브라우저가 무한 루프에 빠지지 않고, 휠 스크롤의 부드러움(FPS) 및 전체 네트워크 대기 딜레이가 즉각적으로 개선된 것을 확인했습니다.
