---
title: "OPDS 다운로드 시 EPUB/ZIP 파일 형식 다운로드 오류 수정"
date: "2026-07-06"
type: "bugfix"
status: "completed"
tags: ["opds", "download", "mime"]
---

# OPDS 다운로드 시 EPUB/ZIP 파일 형식 다운로드 오류 수정

## 1. 개요 및 증상
- **현상**: 외부 OPDS 뷰어 앱(Tachiyomi, KyBook, Chunky Reader 등)을 통해 EPUB 혹은 ZIP(만화책 CBZ) 도서를 다운로드하려고 시도할 때, 다운로드 버튼이 작동하지 않거나, 파일이 정상적으로 다운로드된 직후 리더 앱이 "지원하지 않는 형식이거나 손상된 파일"이라며 읽기 동작이 실패하는 현상이 다수 보고되었습니다.

## 2. 원인 분석
- **Atom XML 피드 MIME 오류**: OPDS 카탈로그 피드 데이터(`opds_service.py`) 내에서 파일의 형식을 외부 앱에 전달해 주기 위해 파이썬 내장 라이브러리인 `mimetypes.guess_type`을 사용하고 있었습니다. 그러나 윈도우나 리눅스 등 기본 서버 운영체제 레지스트리 상태에 따라 `.epub`이나 `.cbz` 확장자의 MIME Type이 등록되어 있지 않은 경우 `application/octet-stream` 형식으로 임의 대체되어 외부 리더 앱이 다운로드를 허용하지 않거나 파일을 인지하지 못했습니다.
- **다운로드 응답 헤더 누락**: 실제 파일 다운로드를 수신받는 `/opds/download/` 엔드포인트에서 단순히 `send_file(file_path, as_attachment=True)`만 리턴하고 명시적인 `mimetype` 및 파일 이름 헤더가 전달되지 않아 다운로드 완료 후 확장자 유실이 동반되었습니다.

## 3. 해결 방안
- [opds_service.py](file:///c:/project/media_server/services/opds_service.py): `_guess_mime_type` 헬퍼 함수를 고도화하여 `.epub`, `.cbz`, `.cbr`, `.zip` 등 주요 전자책/만화책 확장자에 대한 표준화된 규격 MIME Type을 하드코딩 맵 테이블 형태로 직접 바인딩하여 OS 종속성을 회피하도록 구현했습니다.
  - `.epub` ➔ `application/epub+zip`
  - `.cbz` ➔ `application/x-cbz`
  - `.cbr` ➔ `application/x-cbr`
- [api/opds.py](file:///c:/project/media_server/api/opds.py): 다운로드 응답 빌드 시 `download_name`에 실제 물리 파일명을 명시하고, 추출된 커스텀 `mimetype`을 강제로 `Content-Type` 헤더로 주입해 전송 신뢰성을 올렸습니다.

## 4. E2E 검증 결과
- 표준 OPDS 클라이언트 연동 테스트 진행 결과, EPUB 및 ZIP 형식의 파일 다운로드 요청 시 전송 프로토콜 헤더에 지정된 규격 정보가 정확하게 탑재되고(예: `Content-Type: application/epub+zip`), 수신 이후 리더 앱 내부 보관함에 온전하게 보관 및 즉시 열람이 가능함을 최종 확인했습니다.
