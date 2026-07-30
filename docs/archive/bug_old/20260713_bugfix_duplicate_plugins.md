---
title: "대시보드 플러그인 탭 중복 노출 오류 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, dashboard, plugin, layout, concurrency]
---

# 대시보드 플러그인 탭 중복 노출 오류 수정

## 1. 버그 내역 및 증상
- 대시보드의 '플러그인' 탭 메뉴에 진입할 때, 상단 탭 버튼(독서 통계, 최근 사용자 활동 등) 및 하부 위젯 카드 레이아웃이 2개씩 중복 노출되는 현상 제보.

## 2. 원인 분석
- `static/js/dashboard.js` 내 `loadDashboardPlugins` 함수가 여러 번 연속 호출되는 경우, 기존에는 비동기 처리 완료 후 `dashboardLoadToken`의 정적 상태만 조회하여 비교 작업을 하고 있었음.
- 그러나 `loadDashboardPlugins`가 동작할 때는 `dashboardLoadToken`이 증가하지 않고 그대로 유지되므로, 연달아 발생한 비동기 작업 결과들의 토큰이 모두 동일하여 중복 그리기가 수행됨.

## 3. 조치 사항
- **플러그인 전용 동시성 제어 토큰 적용 (`static/js/dashboard.js`)**:
  - 플러그인 전용 비동기 요청 취소용 토큰 카운터 변수인 `pluginsLoadToken`을 신설함.
  - `loadDashboardPlugins` 실행 시마다 `pluginsLoadToken`을 1씩 선행 가산하여 고유 요청 식별자로 삼음.
  - API 비동기 처리 응답 시점 및 하위 루프 동작부마다 `currentToken !== pluginsLoadToken` 여부를 체크하여, 최신으로 갱신된 요청이 아닌 과거의 비동기 흐름은 UI 렌더링에 도달하지 못하고 조기 반환(`return`)되도록 원천 차단함.
  - 하부 위젯 데이터를 조회하는 `loadDashboardWidgetData`에서도 신설된 `pluginsLoadToken`을 매핑하여 연계 검증하도록 개선함.

## 4. 해결 확인 및 영향도
- 로컬 웹브라우저에서 플러그인 메뉴 탭을 빠르게 수차례 클릭하여 강제로 동시 다발적 요청을 생성한 상태에서도 중복 렌더링되지 않고 1개의 정상적인 플러그인 탭 세트만 화면에 단독 노출되는 것을 최종 확인 및 완료함.
