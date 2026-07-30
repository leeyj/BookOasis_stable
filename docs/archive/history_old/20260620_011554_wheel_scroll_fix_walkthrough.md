---
title: Walkthrough - wheel_scroll_fix
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 휠 스크롤 및 페이지 전환 제어 버그 수정 결과 (Walkthrough)

미디어 뷰어 휠 스크롤 불가능 버그와 마우스 휠 폭주(무한 페이지 전환) 문제를 해결하고 성공적으로 검증을 완료하였습니다.

## 변경 사항 요약 (Changes)

### 뷰어 코어 조율기

#### [viewer.js](file:///c:/project/media_server/static/js/viewer.js)
- `initWheelListener` 함수를 추가하여 뷰어 기동 시 마우스 휠 감지 시스템을 활성화하였습니다.
- 뷰어 위에 배치된 공통 핫스팟 레이어(`common-viewer-hotspot`)에 휠 이벤트 리스너를 결합하여, 핫스팟 레이어로 인해 마우스 휠 스크롤이 차단되는 현상을 근본적으로 해결했습니다.
- **세로 스크롤 모드**: 텍스트 뷰어(`txt-scroll-wrapper`), 만화 너비맞춤(`comic-image-wrapper`), PDF(`pdf-render-area`), EPUB(iframe contentWindow) 각각에 맞추어 마우스 휠 입력을 `scrollBy` 방식으로 정확하게 바이패스 전파했습니다.
- **가로 페이지 모드**: 마우스 휠 폭주(무한 페이지 넘김) 현상을 조율하기 위해 `wheelLock` 플래그 및 `setTimeout` 타임락(600ms) 쓰로틀링 필터를 탑재하여 안정적으로 한 페이지씩 전환되도록 개선했습니다.

## 검증 결과 (Verification Results)
- **만화 ZIP 뷰어**: '높이맞춤' 모드에서 마우스 휠을 내리거나 올릴 때 한 페이지씩 600ms 딜레이를 두며 정확히 페이지가 넘어가고, '너비맞춤(웹툰)' 모드에서는 세로 방향으로 부드럽게 세로 휠 스크롤이 작동합니다.
- **텍스트 TXT 뷰어**: 가로 페이지 모드에서는 휠 동작 시 다음/이전 청크로 알맞게 페이징되며, 세로 스크롤 모드에서는 텍스트 내용이 휠을 따라 매끄럽게 스크롤됩니다.
- **기본 라이브러리 목록**: 뷰어가 종료된 상태에서 메인 화면(도서 목록 그리드)의 휠 스크롤도 원상 복구되어 정상 기능하는 것을 확인했습니다.
