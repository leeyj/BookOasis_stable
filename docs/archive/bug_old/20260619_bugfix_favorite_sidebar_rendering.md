---
title: "즐겨찾기 사이드바 메뉴 미노출 장애 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-19
tags: [bugfix, favorite, sidebar]
---

# 🐛 즐겨찾기 사이드바 메뉴 미노출 장애 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- HTML 템플릿에 추가했던 `즐겨찾기` 탭이 페이지가 로딩될 때 사이드바 목록에서 사라져 미노출됨.

## 2. 원인 분석 (Root Cause Analysis)
- `static/js/category.js` 파일 내의 `loadLibraries` 함수에서 라이브러리 목록을 비동기 조회한 후, 사이드바의 HTML 전체를 하드코딩된 시스템 메뉴 조합(`Home`, `최근 읽은 도서`, `전체보기`)으로 덮어씌움.
- 이 과정에서 즐겨찾기(`favorite`) 탭이 HTML 갱신 문자열에서 누락되어 소멸함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: `static/js/category.js`
- `loadLibraries()` 함수 내 시스템 메뉴 HTML 빌드 변수(`html`) 구성 시, `favorite` 탭 요소를 추가하여 덮어쓰기 시에도 정상 노출되도록 보완함.
  ```javascript
  html += `<li class="menu-item ${state.currentLibraryId === 'favorite' ? 'active' : ''}" data-type="system" id="category-favorite" data-id="favorite" onclick="selectCategory('favorite')"><i class="fa-solid fa-star" style="color: #eab308;"></i> 즐겨찾기</li>`;
  ```

## 4. 결과 검증 (Verification Results)
- 소스 코드 동기화 후, 사이드바에 '즐겨찾기' 아이콘이 정상적으로 항상 유지되어 정상 노출됨을 확인함.
