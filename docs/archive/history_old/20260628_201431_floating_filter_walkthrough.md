---
title: Walkthrough - floating_filter
project: BookOasis
category: history
date: 2026-06-28
type: walkthrough
---
# 작업 결과 요약 (Walkthrough)

대량의 장르/태그 탐색 효율성을 극대화하기 위해, 드래그 이동과 실시간 칩 검색이 지원되는 반투명(Glassmorphism) 플로팅 모달창 기반의 상세 필터 기능을 구현 완료하였습니다.

## 🛠️ 수정 사항

### 1. 필터 모달 마크업 설계 ([tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html#L68-L72))
- 검색바 영역에 `<button id="btn-open-filter">` (필터) 버튼을 배치하였습니다.
- 화면의 기존 레이아웃 구성을 가리지 않고 가시성을 살려 배치할 수 있는 `floating-filter-modal` 반투명 제어판 마크업을 구축했습니다.

### 2. 글래스모피즘 CSS 스타일링 ([tab_media_library_viewer.css](file:///c:/project/media_server/static/css/tab_media_library_viewer.css#L644-L880))
- 둥둥 뜨는 반투명 뷰를 연출하기 위해 `backdrop-filter: blur(12px) saturate(160%)`와 부드러운 트랜지션 애니메이션을 입혔습니다.
- 드래그 이벤트를 식별하도록 헤더에 `cursor: move` 및 선택 칩에 대한 Active / Hover 인터랙션 디자인을 추가했습니다.

### 3. 드래그 앤 드롭 및 실시간 인라인 칩 검색 기능 ([genre_tag_filter.js](file:///c:/project/media_server/static/js/genre_tag_filter.js))
- **패널 이동 드래그 스크립트**: 헤더를 마우스 드래그하여 패널 위치를 모니터 화면 내에서 자유롭게 배치할 수 있는 자바스크립트 좌표 제어 로직을 작성했습니다.
- **칩 실시간 검색**: 수백 개가 넘는 태그들 중 원하는 칩을 빨리 찾아낼 수 있도록 인라인 검색창을 탑재하여 글자를 치는 즉시 해당 칩만 필터링되도록 처리했습니다.
- **다중 선택 조건 결합**: 장르와 태그를 동시에 다중 선택할 수 있도록 배열 기반 상태(`Set`)를 관리하고 적용 시 교집합(AND) 논리로 그리드 뷰를 연동 필터링합니다.

---

## 🧪 E2E 최종 검증 결과
- **정상 작동 확인**: '필터' 단추를 클릭하면 반투명 모달 패널이 매끄러운 페이드인과 함께 기동하며, 드래그하여 원하는 위치로 자유롭게 이동시킬 수 있음을 확인했습니다.
- **칩 다중 필터링 적용**: 검색창에 초성을 입력하여 매칭 칩들이 부드럽게 재배치되고, 장르와 태그 칩을 동시에 다중 선택한 뒤 '적용'을 누르면 도서 목록 그리드가 완벽히 실시간 필터링되는 E2E 연동성을 최종 확인하였습니다.
