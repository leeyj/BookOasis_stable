---
feature_id: feat_download_button_epub_pdf_txt
date: 2026-07-22
type: feature
affected_files:
  - api/library.py
  - static/js/detail_render.js
  - static/js/modal.js
  - static/css/style.css
  - static/css/mobile.css
  - static/i18n/ko.json
  - static/i18n/en.json
---

# Feature: EPUB/PDF/TXT 다운로드 버튼 추가

## 개요
도서 상세 화면에서 EPUB, PDF, TXT 포맷에 한해 "이어보기" 버튼 옆에 **다운로드** 버튼을 추가합니다.
iOS의 "도서(Books)" 앱 등 외부 리더 앱에서 바로 열 수 있도록 `Content-Disposition: attachment` 응답을 제공합니다.

## 변경 사항

### 백엔드 (`api/library.py`)
- `GET /api/media/books/<book_id>/download?type=<db_type>` 엔드포인트 추가
- epub / pdf / txt 포맷만 허용 (그 외 400 반환)
- rclone 원격 마운트 경로도 `os.path.exists()` 기반으로 직접 서빙 가능 (FUSE 마운트 방식이므로 로컬 I/O 동일)
- `send_file(as_attachment=True)` 로 브라우저/iOS 다운로드 트리거

### 프론트엔드 (`static/js/detail_render.js`, `modal.js`)
- `renderVolumesList(books, safeSeriesName, actualLibraryId, dbType)` 에 `dbType` 파라미터 추가
- epub/pdf/txt 포맷인 경우 `.btn-read-row` flex 컨테이너로 이어보기(flex:1) + 다운로드(고정폭) 버튼 나란히 배치
- 그 외 포맷(zip, imgdir 등)은 기존 전체 너비 단일 버튼 유지

### CSS (`style.css`, `mobile.css`)
- `.btn-read-row`: flex row 컨테이너 (gap 0.5rem)
- `.btn-download`: 청록(sky blue) 계열 그라디언트 스타일, hover 애니메이션 포함
- 모바일: `.btn-read-row` 100% 너비, 버튼들 균형 배분

### i18n (`ko.json`, `en.json`)
- `detail.btn_download` 키 추가 (ko: "다운로드" / en: "Download")

## rclone 경로 다운로드 가능 여부
rclone은 FUSE 마운트 방식으로 로컬 파일시스템에 노출되므로
`open(file_path, 'rb')` / `send_file()` 모두 정상 동작합니다.
기존 뷰어 스트리밍 방식(`stream_file_safely`)과 동일한 접근 방식입니다.
