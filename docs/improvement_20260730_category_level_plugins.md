---
title: "카테고리 레벨 플러그인 아키텍처 구현 및 샘플(독서 통계 센터) 풀페이지 승격"
date: 2026-07-30
category: improvement
tags: [plugin, category_level, sidebar, stats_dashboard, fullpage_ui]
impact: high
status: completed
---

# 개선 내역: 카테고리 레벨 플러그인 아키텍처 구현 및 독서 통계 센터 풀페이지 승격

## 개요
대시보드 미니 위젯 카드 수준에 머무르던 플러그인을 **좌측 사이드바 1등 시민(First-class Citizen) 카테고리 메뉴**로 등록하고, 메인 영역 전체 화면에 풀페이지 커스텀 UI를 마운트할 수 있는 카테고리 레벨 플러그인 확장 엔진을 구현했습니다.

## 주요 변경 사항

### 1. 백엔드 매니페스트 및 UI 엔드포인트 구현 (`services/metadata_factory.py`, `api/library.py`)
- **`category_tab` 매니페스트 파싱**:
  - 플러그인 클래스 내 `category_tab = {'title': '...', 'icon': '...', 'order': 90}` 선언 파싱.
- **카테고리 플러그인 목록 조회 API (`GET /api/media/category-plugins`)**:
  - 활성화된 카테고리 레벨 플러그인 및 UI 번들 서빙.
- **플러그인 UI 번들 API (`GET /api/media/plugins/<plugin_id>/ui`)**:
  - `index.html`, `style.css`, `script.js` 템플릿 번들을 안전하게 반환.

### 2. 프론트엔드 사이드바 주입 및 풀페이지 마운터 (`static/js/category.js`, `tab_media_library.js`, `view_manager.js`)
- **사이드바 동적 주입**:
  - 사이드바 카테고리 렌더링 시 활성화된 카테고리 레벨 플러그인을 동적으로 추가.
- **`#library-plugin-custom-view` 풀페이지 마운터**:
  - 사이드바 카테고리 클릭 시 메인 화면 영역 전체를 커스텀 플러그인 뷰로 전환하고 UI 번들을 동적 마운트.

### 3. 샘플 플러그인 승격: 독서 통계 센터 (`plugins/metadata/stats_dashboard`)
- `stats_dashboard` 플러그인에 `category_tab` 추가.
- `index.html`, `style.css`, `script.js`를 작성하여 **"📊 독서 통계 센터"** 종합 리포트 풀페이지 화면 구현.

### 4. 플러그인 개발 가이드 문서화 갱신 (`docs/guide_plugins.md`, `docs/guide_plugins_en.md`)
- `category_tab` 작성 규격 및 HTML5 풀 태그(Canvas, SVG, Table, Form 등) 100% 해제 지원 규정 명시.
