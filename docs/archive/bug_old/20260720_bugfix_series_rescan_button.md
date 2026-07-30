---
id: "20260720_bugfix_series_rescan_button"
date: 2026-07-20
category: "bugfix"
severity: "medium"
status: "fixed"
tags: [rescan, ui, detail_view, ux]
---

# 20260720 — 시리즈 상세 리스트에서 "이 시리즈 재스캔" 버튼 누락 버그 수정

## 버그 내역

### 현상
- 도서 상세 리스트 화면에서 사용자가 시리즈 단위로 전체 도서를 재스캔할 수 있는 "이 시리즈 재스캔" 버튼이 보이지 않음.
- 실제로 "모두 재스캔(btn_rescan_all)" 버튼이 존재했으나, 페이지 누락 등의 에러가 발생한 도서가 시리즈 내에 존재하는 경우에만 배너 형태로 한정되어 노출됨. 에러가 없는 일반 상황에서 사용자가 시리즈 전체를 다시 스캔하고 싶을 때 버튼에 접근할 수 없었음.

### 근본 원인
- 시리즈 단위의 강제 재스캔 기능이 상세 화면의 일반 액션 영역(헤더 버튼 그룹)에 배치되지 않고, 오류 상태 경고 배너 내에만 종속되어 있었음.

## 영향도
- 사용자는 오류가 없는 시리즈에 대해 표지 변경이나 파일 변경 등으로 인한 시리즈 전체 재스캔을 임의로 수행할 수 없었음.

## 수정 사항

### 수정 파일 목록

#### `static/js/modal.js`
- `window.rescanSeries` 전역 헬퍼 함수 추가: 상세 뷰의 `.volume-card`들로부터 모든 책 ID를 추출하여 `api.scanSingleBook`을 순차적으로 호출한 뒤 페이지를 새로고침.

#### `static/js/detail_render.js`
- `renderDetailHeader`의 상단 버튼 랙 영역에 "이 시리즈 재스캔" 버튼을 배치.

#### `static/i18n/ko.json` / `en.json`
- `"detail"` 키에 `"btn_rescan_series"` 번역 추가.
  - ko: `"btn_rescan_series": "이 시리즈 재스캔"`
  - en: `"btn_rescan_series": "Rescan Series"`

## 해결 사항
- 도서 상세 리스트 모달 진입 시 상단에 "이 시리즈 재스캔" 버튼이 항상 노출되며, 이를 클릭하여 시리즈 전체 도서를 수동으로 재스캔할 수 있음.
