# 버그 내역 및 해결 사항: 모바일 텍스트/EPUB 뷰어 스크롤 모드에서 컨텍스트 메뉴가 제일 상단에 고정되는 버그

## 버그 내역 (Bug Description)
모바일 환경에서 TXT(텍스트) 뷰어 및 EPUB 뷰어를 스크롤 모드로 사용할 때, 화면 중앙을 탭해 컨텍스트 메뉴(오버레이 메뉴)를 열면 현재 보고 있는 위치가 아닌 페이지 **최상단(scroll top=0)**에 메뉴가 표시되는 현상이 있었습니다.

## 원인 분석 (Root Cause)
스크롤 모드에서는 `viewer-modal` 요소 자체에 `scroll-mode-active` 클래스가 부여되어 `overflow-y: auto`가 활성화됩니다. 즉, 뷰어 모달 컨테이너가 스크롤 컨테이너 역할을 하게 됩니다.

이 상태에서 오버레이 메뉴는 `position: fixed`로 선언되어 있어 본래 현재 뷰포트 기준으로 고정되어야 합니다. 하지만 **iOS Safari (및 backdrop-filter가 적용된 부모 요소)** 환경에서는 `position: fixed`가 **가장 가까운 스크롤 컨테이너(여기선 `viewer-modal`)의 최상단을 기준**으로 고정되어 버리는 하드웨어 가속/렌더링 경계 문제가 있습니다. 결과적으로 뷰어를 스크롤한 만큼 이동된 절대 좌표 상단에 메뉴가 고정됩니다.

## 수정 사항 (Modifications)
- **수정된 파일**: `static/js/viewer/navigation.js`
- **구현 방식**: 
  - `toggleComicOverlay()` 함수 내에서 메뉴를 여는 시점(`isOpening === true`)에, `viewer-modal`의 현재 `scrollTop` 값을 읽어 오버레이 메뉴의 `style.top`에 동적으로 더해주는 방식으로 현재 스크롤 위치를 보상(offset)합니다.
  - 플로팅 닫기 버튼(`floating-close-btn`) 및 PDF/EPUB 네비게이션 바도 동일한 오프셋 보정 로직을 적용했습니다.
  - 메뉴를 닫을 때는(`isOpening === false`) 동적으로 삽입한 `top` 스타일을 초기화합니다.
  - 이전 수정에서 변수 선언 전 사용(use-before-declaration) 오류가 발생한 것을 함께 수정했습니다.

## 해결 사항 (Resolution)
스크롤 모드에서 화면 중앙을 터치해 컨텍스트 메뉴를 열면, 현재 독서 중인 위치의 뷰포트를 기준으로 정확하게 오버레이 메뉴가 표시됩니다.
