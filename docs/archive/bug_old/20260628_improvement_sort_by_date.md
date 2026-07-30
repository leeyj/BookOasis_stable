---
title: "도서 파일 추가일(생성일) 기준 정렬 기능 추가"
project: "BookOasis"
category: "general"
date: 2026-06-28
tags: [improvement, sort, ui]
---

## 🚀 개선 내역 (Improvement)
- 기존 가나다(자연 정렬) 오름차순/내림차순만 지원하던 도서 목록 화면에 **최신 추가순(date_desc)** 및 **과거 추가순(date_asc)** 정렬 옵션을 추가했습니다.
- 서버단에서 이미 수집하여 반환 중이던 DB 삽입 날짜(`latest_added`, DB의 `created_at`) 속성을 클라이언트 사이드 로컬 정렬에서 재활용하여 서버 추가 부하 없이 즉시 정렬되도록 구현했습니다.

## 📌 영향도 (Impact)
- 프론트엔드 UI의 정렬 토글 버튼을 4가지 상태 주기(오름차순 -> 내림차순 -> 최신 추가순 -> 과거 추가순)로 순환하도록 수정되었습니다.
- 클라이언트단 `sortBooksList` 헬퍼 함수가 추가되어 여러 곳에 산재해있던 로컬 정렬 로직이 일원화되었습니다.
- 검색, 장르 필터 등과 정상적으로 함께 작동합니다.

## 🛠️ 수정 사항 (Changes)
- `static/js/book_list.js` :
  - `sortBooksList` 헬퍼 함수 구현 및 반영
  - `toggleLibrarySort` 함수에 `date_desc`, `date_asc` 상태 처리 추가
- `templates/components/tab_media_library.html` :
  - 정렬 버튼의 `title` 속성 및 내부 텍스트 명시성 강화 ("가나다 오름차순")

## ✅ 해결 사항 (Resolution)
- 사용자가 원하는 방식으로 도서 보관함의 시리즈/단행본 목록을 추가 시점 기준으로 정렬하여 볼 수 있게 되었습니다.
