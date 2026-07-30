---
name: dashboard_recently_added_grouped
description: 대시보드 신규 추가 도서 목록에서 시리즈 단위로 그룹화하여 묶어 보여주는 기능 개선
---

# 📚 [기능개선] 신규 추가 도서 대시보드 내 시리즈(Series) 단위 묶음 노출 처리

대시보드 메인 화면의 '신규 추가 도서' 섹션에서 도서들이 개별 권수(Volume)별로 전부 나열되던 중복 노출 현상을 시리즈 단위로 묶어서 가장 최신 추가된 한 권의 대표 정보만 표시하도록 쿼리를 최적화했습니다.

## 1. 개요 및 분석
* **현상**: 여러 권으로 이루어진 시리즈(예: `히어로인즈 게임` 1, 2, 3권 등)가 한 번에 스캔되어 등록되었을 때, 신규 추가 도서 목록에 각각의 단권 카드가 개별 노출되어 화면을 다수 점유했습니다.
* **해결 방안**: 데이터베이스에서 최근 등록 도서를 조회할 때, `series_name`이 있는 책들은 시리즈명을 기준으로 그룹화(`GROUP BY`)하여 그 중 가장 최신의 권(ID가 가장 큰 항목)만 대표 카드로 노출하고, 시리즈명이 없는 개별 단행본은 단권 독립 카드로 노출합니다.
* **UX 연동**: 대시보드의 도서 카드를 클릭할 때 시리즈명(`series_name`)이 존재하는 경우 프론트엔드가 이를 자동 감지하여 시리즈 전체 도서가 모여 있는 '도서 상세 뷰(openBookDetail)'로 이동하고, '바로읽기' 버튼 클릭 시 가장 최신 권수가 실행되도록 최적화되어 있으므로, 쿼리 묶음 적용만으로 자연스럽고 완벽하게 연동됩니다.

## 2. 해결 방법
* **[services/reading_history_service.py](file:///c:/project/media_server/services/reading_history_service.py)**:
  * `get_recently_added()` 메소드 내부의 단순 `ORDER BY created_at` 쿼리를 서브쿼리 그룹화 구조로 리팩토링했습니다.
  * `series_name`이 채워진 행은 시리즈명으로 그룹핑하고, 비어있는 행은 각 고유 `id` 기준으로 그룹핑하여, 그룹 내 가장 최신의 `id`를 가진 `books` 정보를 가져오도록 `INNER JOIN`을 구현했습니다.

## 3. 수정 파일 목록
* [services/reading_history_service.py](file:///c:/project/media_server/services/reading_history_service.py#L46-L71)
