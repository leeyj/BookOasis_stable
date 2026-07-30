---
title: "모바일 뷰 레이아웃 및 버전 파싱 결함 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, mobile, css, layout, version]
---

# 모바일 뷰 레이아웃 및 버전 파싱 결함 조치

## 1. 버그 내역 및 증상
1. **최신 배포 버전 파싱 실패 (PC/모바일 공통)**: 환경설정의 '이 S/W는...' 탭에서 최신 배포 버전을 가져오지 못하고 "버전 파싱 실패"가 상시 노출됨.
2. **삭제관리 탭 모바일 뷰 버튼 깨짐**: 환경설정 -> 삭제관리 탭의 상단 영역에서 복구/삭제 버튼들의 너비가 좁아지면서 텍스트가 세로로 한 글자씩 끊겨서 출력됨. 또한 테이블 영역도 가로 크기가 줄어들면서 찌그러지는 현상 발생.
3. **단축키 설정 초기화 버튼 미노출**: 환경설정 -> 단축키 설정 영역의 가로 폭이 부족하여 "초기화" 버튼이 모바일 뷰포트 영역 바깥으로 밀려 보이지 않는 현상 발생.
4. **스캔 예약(Queue) 대기열 조회 버튼 세로 일그러짐**: 대기열 조회 탭의 우측 상단 '큐 일괄 삭제' 및 '새로고침' 버튼이 모바일 뷰포트 폭 축소 시 세로로 길쭉하게 찌그러지고 글자가 깨지는 현상 발생.

## 2. 원인 분석
1. **버전 파싱 정규식 불일치**: `static/js/settings_tab.js`의 `loadAboutInfo()` 내 최신 버전 추출 정규식(`/"dashboard":\s*([0-9\.]+)/`)이 로컬 및 원격 `VERSION` 파일 내용인 `"dashboard": "0.9.6"`의 우측 따옴표(`"`)를 배제하고 파싱하려 하여 매칭에 실패함.
2. **flexbox 컨테이너의 반응형 랩핑 사양 누락**:
   - 삭제관리 탭 상단의 컨트롤 패널이 `justify-content: space-between; align-items: center` 인라인 flex 속성만 적용되어 있어 가로 폭 부족 시 축소되거나 버튼들이 구겨짐.
   - 단축키 설정 컨테이너 역시 좁은 화면에서 하위 요소들이 강제로 한 줄로 나열되면서 마지막 버튼인 '초기화' 버튼이 바깥으로 삐져나옴.
   - 스캔 대기열 조회 헤더 역시 우측에 배치된 버튼 영역이 좌측 문구 영역에 밀려 압착되면서 버튼 내부 텍스트가 강제로 일그러짐.

## 3. 조치 사항
1. **버전 파싱 정규식 개선 (`static/js/settings_tab.js`)**:
   - GitHub raw VERSION 파일 값의 구조에 맞추어 따옴표를 포함하도록 정규식을 `/"dashboard":\s*"([0-9\.]+)"/` 로 교정하여 버전을 정상적으로 캡처하도록 수정.
2. **삭제관리 탭 반응형 레이아웃 보완 (`templates/components/settings/trash_tab.html`, `static/css/mobile.css`)**:
   - 삭제관리 상단 헤더에 `trash-header-container`, 버튼 묶음에 `trash-header-buttons` 클래스를 추가.
   - 모바일 뷰포트(max-width: 768px)일 때 컨트롤 패널을 세로 배열(`flex-direction: column`)로 전환하고 버튼들이 가로 균등 분할되도록 스타일 재정의.
   - 테이블 컨테이너에 `settings-table-wrapper`와 `settings-table` 클래스를 적용하여 모바일 뷰포트에서 다른 탭처럼 자연스럽게 가로 스크롤되도록 구조 변경.
3. **단축키 설정 버튼 랩핑 보완 (`templates/components/settings/general_tab.html`, `static/css/mobile.css`)**:
   - 단축키 설정 레이아웃에 `shortcut-controls-wrap` 클래스를 부여.
   - 모바일 뷰포트에서 `flex-wrap: wrap`을 적용하고 입력란은 100% 가로 너비를 점유하며, '기록 시작', '초기화' 버튼이 아래 줄에 절반씩 균등 배치되도록 하여 가독성과 터치성을 고도화.
4. **스캔 대기열 버튼 배치 조정 및 일그러짐 조치 (`templates/components/settings/queue_tab.html`, `static/css/mobile.css`)**:
   - 대기열 조회 헤더에 `queue-section-header`, 버튼 묶음에 `queue-header-buttons` 클래스를 부여.
   - 모바일 뷰포트(max-width: 768px) 기준, 헤더 방향을 세로(`flex-direction: column`) 및 왼쪽 정렬로 전환하여 버튼들을 설명 메시지 아래로 재배치하고, 가로 영역을 균등 분할하여 텍스트 깨짐 없이 정상 출력되도록 반응형 CSS 구현 완료.

## 4. 해결 확인 및 영향도
- PC 및 모바일 브라우저 개발자 도구의 Device Mode를 활용하여 320px ~ 768px 구간의 해상도를 집중 검증.
- 최신 배포 버전이 실패 메시지 대신 `v0.9.6`으로 정상 노출되는 것을 확인.
- 삭제관리 탭, 단축키 설정 영역, 스캔 대기열 조회 영역의 모든 버튼들이 잘리거나 깨지지 않고 올바른 반응형 스타일로 정렬 및 배치되는 것을 최종 확인.
