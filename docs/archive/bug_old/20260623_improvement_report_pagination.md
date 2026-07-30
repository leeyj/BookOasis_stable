---
title: "스캔 리포트 뷰어 대용량 에러 페이징 처리"
project: "BookOasis"
category: "improvement"
date: 2026-06-23
tags: [ui, performance, report, pagination]
---
# 개선 내역
스캔 에러 리포트에 수만 건의 오류(예: 70,000건 이상)가 누적되어 있을 경우, 웹 뷰어에서 이를 한 번에 DOM 요소로 렌더링하려다 브라우저가 메모리 부족으로 다운되거나 프리징 현상이 발생하는 문제를 해결.

# 원인
`static/js/settings/reports.js` 의 `loadReportDetail()` 함수에서 JSON으로 받아온 전체 에러 배열을 순회하며 모든 행(`<tr>`)을 한 번에 생성하여 `innerHTML`에 삽입하고 있었음. 이로 인해 대용량 데이터 로드 시 브라우저 성능 저하 및 크래시 발생.

# 수정 사항
1. **`templates/components/settings/reports_tab.html` 수정**
   - 에러 리스트 테이블 하단에 페이지네이션 버튼이 위치할 `div#report-pagination-container` 요소 추가.
2. **`static/js/settings/reports.js` 수정**
   - 전역 상태 관리 변수(`currentReportErrors`, `currentReportPage`, `ITEMS_PER_PAGE=50`) 추가.
   - `loadReportDetail()` 호출 시 서버에서 가져온 전체 에러 데이터를 `currentReportErrors` 배열에 저장하고, 현재 페이지에 해당하는 50개 항목만 잘라서(`slice`) 렌더링하는 `renderReportPage()` 함수 구현.
   - 게시판 형태처럼 하단에 이전/다음 및 페이지 번호(최대 5개 노출)를 렌더링하는 로직 구현.
   - `window.changeReportPage(page)` 전역 함수를 바인딩하여 페이지 이동 시 DOM만 즉각 업데이트 하도록 연동.

# 해결 사항
에러 리포트가 수만 건이 되더라도 한 화면에는 50건의 행만 렌더링되므로 브라우저 성능이 크게 개선되며 다운 현상이 원천 차단됨. 사용자는 하단의 번호 이동 버튼을 통해 끊김 없이 편안하게 에러 내역을 훑어볼 수 있음.
