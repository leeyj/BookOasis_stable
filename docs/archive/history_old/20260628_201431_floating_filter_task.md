---
title: Task - floating_filter
project: BookOasis
category: history
date: 2026-06-28
type: task
---
# 작업 계획 (Task)

- [x] HTML 템플릿 (`templates/components/tab_media_library.html`) 레이아웃 구성
  - [x] 상단 제어바에 필터 토글 버튼 추가
  - [x] 둥둥 뜨는 반투명(Glassmorphism) 모달창 마크업 구현
- [x] CSS 스타일 (`static/css/tab_media_library_viewer.css`) 설계
  - [x] 반투명 블러 백그라운드 및 드래그 핸들 전용 디자인 추가
  - [x] 선택 칩(Selected Chip) 배지 및 모달 토글 트랜지션 애니메이션 정의
- [x] JS 핵심 모듈 (`static/js/genre_tag_filter.js`) 기능 구현
  - [x] 모달창 드래그 앤 드롭 자유 이동 스크립트 작성
  - [x] 장르 및 태그 API 데이터 로드 및 칩 컴포넌트 렌더링
  - [x] 검색 인풋창 실시간 칩 검색 필터 구현
  - [x] 칩 다중 선택 토글 및 그리드 뷰 필터링 조건 연동
- [x] JS 메인 컨트롤러 (`static/js/tab_media_library.js`) 연동
  - [x] 장르/태그 검색 쿼리 상태를 메인 도서 필터링 함수와 결합하여 갱신
- [x] E2E 동작 검증 및 아카이빙
  - [x] 최종 화면 배포 후 기동 테스트 및 모달 드래그, 칩 검색 작동 확인
  - [x] walkthrough.md 갱신 및 collect_docs.py 실행
