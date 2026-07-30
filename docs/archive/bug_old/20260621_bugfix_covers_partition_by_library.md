---
title: "표지 폴더 카테고리별 분할화 및 DB 경로 격리를 통한 표지 유실/중복 문제 근본 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [scanner, cover, database, fallback, refactor]
---

# 🐛 표지 폴더 카테고리별 분할화 및 DB 경로 격리를 통한 표지 유실/중복 문제 근본 조치 (Bugfix Report)

## 1. 버그 내역 및 현상
- **현상**: 여러 카테고리에 동일한 시리즈의 책들이 중복 등록(예: GDRIVE, NAS 등)되어 있는 경우, 특정 카테고리의 책들만 표지가 유실/미스캔되었더라도 도서 보관함 목록 카드 전체가 기본 이미지(책 펼쳐진 이미지)로 표시되는 버그가 발생했습니다.
- **원인**:
  1. 단일 디렉터리 `/covers/`에 21만 개가 넘는 표지 파일들이 무계획적으로 저장되어 OS 레벨의 탐색 오버헤드가 발생했습니다.
  2. DB 테이블(`books`)에는 파일명이 아닌 단순히 문자열만 기입되어 있어 디스크에 물리 표지 파일이 유실되었어도 `ORDER BY title ASC LIMIT 1`에 의해 빈 껍데기 레코드가 대표 표지로 선정되었습니다.
  3. VFS(원격 드라이브) 스캔 시 압축 파일 I/O 스킵으로 인해 표지가 유실되었음에도, DB에는 표지 컬럼이 존재하므로 대표 이미지로 설정되는 현상이 발생했습니다.

## 2. 영향도 및 범위
- **영향 범위**: 전체 도서 목록 조회 API (`/api/books` 및 OPDS 등) 및 스캐너 컴포넌트 전체.
- **영향도**: 도서 목록에서 정상적으로 추출된 표지가 엄밀히 존재하는데도 유실된 레코드의 표지를 매핑해 와 기본 아이콘만 주구장창 로드되어 전반적인 사용자 경험 저하를 야기했습니다.

## 3. 수정 및 해결 사항
- ** covers 격리화 및 상대 경로 저장**:
  - `covers/` 하위에 라이브러리(카테고리) ID 기반 하위 디렉터리를 만들고 이미지 파일들을 분할 저장하도록 `tools/scanner/cover.py` 및 `core.py`를 전면 수정했습니다. (반환 시 `{library_id}/book_{hash}.png` 형태의 상대 경로를 반환합니다.)
- **정적 서빙 라우트 유연화**:
  - `/covers/<path:filename>` 형태의 와일드카드 라우트를 적용하여, 하위 디렉터리 경로 형태의 이미지도 안정적으로 unquote하여 파일 서빙을 진행할 수 있도록 `api/stream.py`를 보완했습니다.
- **서버 단 실존 표지 역추적(Fallback) 구현**:
  - `services/book_service.py` 내의 `get_books_list` 및 `get_all_books_list`에서 SQL 서브쿼리가 반환한 대표 표지가 디스크 상에 유실되었을 경우, 동일 시리즈에 속한 다른 권수들의 표지 중 **디스크에 실제 크기가 0보다 큰 정상 이미지 파일이 존재하는 첫 번째 이미지**를 찾아 목록 대표 이미지로 지정해 주는 Fallback 로직을 설계했습니다.

## 4. 조치 소스 파일 목록
- [cover.py](file:///c:/project/media_server/tools/scanner/cover.py)
- [core.py](file:///c:/project/media_server/tools/scanner/core.py)
- [book_service.py](file:///c:/project/media_server/services/book_service.py)
- [stream.py](file:///c:/project/media_server/api/stream.py)
