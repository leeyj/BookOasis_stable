---
title: Walkthrough - representative_cover_image_mismatch_fix
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 대표 표지 이미지 불일치 수정 결과 (Walkthrough)

리스트 화면의 각 시리즈 카드 썸네일과 클릭 후 진입하는 상세 페이지 헤더의 대표 썸네일이 어긋나는 버그를 DB 쿼리 수준에서 통일하여 수정하였습니다.

## 변경 사항 요약 (Changes)

### 서비스 및 데이터베이스 레이어

#### [MODIFY] [book_service.py](file:///c:/project/media_server/services/book_service.py)
- `get_books_list` 메서드의 SQL 쿼리 구문 중 무작위 썸네일을 집계하던 `MAX(cover_image)` 부분을 서브쿼리로 수정했습니다.
- 이제 동일한 `series_name`을 갖는 단행본 중에서 **제목 사전 순서상 첫 번째(보통 1권)**이면서 표지 이미지가 존재하는 책의 `cover_image`를 리스트 대표 썸네일로 온전히 반환합니다.

## 검증 결과 (Verification Results)
- 로컬 컴파일 성공 및 `deploy.py`를 가동하여 원격 홈 서버 무중단 재시작을 완료했습니다.
- 이제 리스트 카드 표지와 상세 상단 대표 표지가 서로 동일한 1권 이미지로 완벽히 매칭되어 출력됨을 확인했습니다.
