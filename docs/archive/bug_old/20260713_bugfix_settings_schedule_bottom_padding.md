---
title: "스캔 스케줄 및 대기열 통합 탭 하단 여백 가려짐 개선"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [ui, layout, padding]
---

# ⚙️ 스캔 스케줄 및 대기열 통합 탭 하단 여백 가려짐 개선

## 1. 개선 내역 및 증상
- 백그라운드 스캔 작업이 구동될 때 화면 최하단에 나타나는 '시스템 속보 (백그라운드 작업 구동 알림)' 배너로 인하여, 통합 탭의 하단에 위치한 '스캔 예약 대기열 조회'의 마지막 내역이나 조작 버튼 일부가 아래로 가려져 보이지 않는 불편함이 발생했습니다.

## 2. 해결 방안 및 설계
- 스캔 스케줄 및 대기열 통합 탭 내부 컨테이너의 하단에 `padding-bottom: 6rem;` 여백을 안전하게 추가하여, 하단 배너가 표시되더라도 스크롤 시 모든 내용을 가려짐 없이 원활하게 조회할 수 있도록 개선했습니다.

## 3. 조치 사항
- **[templates/components/views/library_settings.html](file:///c:/project/media_server/templates/components/views/library_settings.html)**:
  - `#settings-tab-schedule` 엘리먼트 스타일에 `padding-bottom: 6rem;` 스타일 속성을 부여하여 넉넉한 하방 스크롤 공간을 보장했습니다.

## 4. 해결 확인 및 영향도
- 하단 배너 유무와 상관없이 대기열 목록을 끝까지 스크롤하여 안전하게 볼 수 있게 됨으로써 모바일 및 데스크톱 환경 모두에서 조작 편의성이 완성되었습니다.
