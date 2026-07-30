---
title: "EPUB 뷰어 엔진 경량화 및 텍스트 뷰어 통합 개선"
date: 2026-07-11
tags: [feature, refactoring, epub, viewer]
---

# EPUB 뷰어 엔진 경량화 및 텍스트 뷰어 통합 개선

## 1. 개요 및 배경
- **문제점**: 기존의 `epub.js` 라이브러리는 브라우저 내에서 `iframe`을 렌더링하고 동적으로 레이아웃 리플로우(Reflow)를 연산하여 화면을 분할하는 구조였습니다. 이로 인해 모바일 기기에서의 레이아웃 깨짐, 스크롤 모드에서의 비정상 동작, 초기 로딩 지연 등의 성능 및 사용성 한계가 있었습니다.
- **해결 방안**: 무거운 `epub.js` 라이브러리를 완전히 걷어내고, 백엔드에서 직접 EPUB 압축 파일 내의 콘텐츠(p, br, h1~h6 및 img 등 핵심 마크업)를 파싱하고 정제하여 클라이언트에 제공합니다. 프론트엔드는 기존에 안정적으로 구현된 TXT 뷰어([viewer_txt.js](file:///c:/project/media_server/static/js/viewer_txt.js))를 활용해 EPUB 형식을 가볍게 렌더링하도록 통합합니다.

## 2. 변경 영향도
- **로딩 성능**: 모바일 브라우저에서 무거운 EPUB 전체를 파싱하지 않고 정제된 가벼운 챕터별 HTML 데이터만 받아오므로 초기 로딩 속도 및 메모리 점유율이 획기적으로 개선되었습니다.
- **삽화 및 이미지 렌더링**: EPUB 내부 삽화 및 표지 이미지(`<img>`)의 주소를 서버 측 실시간 스트리밍 주소로 치환하여 본문 내에 정상적으로 렌더링해 줌으로써 시각적 누락이 없습니다.
- **사용자 경험 (UX)**: 기존 텍스트 뷰어의 커스텀 폰트, 테마(라이트/다크/우드 등), 다단 페이징 및 세로 스크롤 설정이 EPUB 도서에도 100% 동일하게 일관성 있게 적용됩니다.
- **배포 프로세스**: 불필요해진 CDN 호출 및 구형 스크립트(15개 파일)를 정리하고, 홈 서버 배포 스크립트([deploy.py](file:///c:/project/media_server/deploy.py))에 명시적 원격지 소거 정책을 추가하여 배포 시 찌꺼기가 남지 않도록 보장합니다.

## 3. 세부 수정 내역 (수정 소스 파일)

### 1) 백엔드: EPUB 직접 파싱 및 정제 API 추가
- **[services/stream_service.py](file:///c:/project/media_server/services/stream_service.py)**:
  - `StreamService.get_epub_content` 메서드 및 `EPUBHTMLParser` 클래스 수정. 이미지 태그(`<img>`) 파싱 기능을 추가하여 상대 경로 이미지들을 posix 절대 경로로 계산한 후 `/api/media/epub-image` 스트리밍 URL로 매핑 변환합니다.
  - `StreamService.extract_epub_resource` 메서드 추가. EPUB zip 아카이브 내에서 지정된 리소스(이미지) 바이너리를 고속으로 읽어 리턴합니다.
- **[api/stream.py](file:///c:/project/media_server/api/stream.py)**:
  - `/api/media/epub` GET 엔드포인트 수정: 호출 시 `book_id`와 `db_type` 파라미터를 넘겨받아 이미지 URL 매핑을 완성시킵니다.
  - `/api/media/epub-image` GET 엔드포인트 신설: EPUB 내부 이미지 파일을 실시간으로 서빙하고 브라우저 캐싱(`Cache-Control`)을 활성화합니다.

### 2) 프론트엔드: 뷰어 컴포넌트 정리 및 통합
- **[templates/components/media_viewer.html](file:///c:/project/media_server/templates/components/media_viewer.html)**:
  - 구형 `#epub-viewer-container` 구조와 네비게이션 버튼을 소거했습니다.
- **[templates/components/tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)**:
  - 외부 CDN 라이브러리 `epub.min.js` 로드 코드를 삭제했습니다.
- **[static/js/viewer.js](file:///c:/project/media_server/static/js/viewer.js)**:
  - EPUB 포맷 디스패치 타겟을 `TxtViewer`로 변경하고, 미사용되는 구형 래퍼 함수(`initEpubViewer`, `clearEpubViewer` 등)들을 stubbing 처리하여 하위 호환성을 유지하면서 `epub.js` 로딩 의존성을 제거했습니다.
- **[static/js/viewer_txt.js](file:///c:/project/media_server/static/js/viewer_txt.js)**:
  - `state.currentViewerFormat`이 `'epub'`일 때 `/api/media/epub`에서 챕터 데이터를 읽어와 `txtChunks`에 바인딩하고, HTML 마크업 및 이미지 태그가 유지되도록 `innerHTML`을 사용해 안전하게 렌더링하도록 뷰어 코어를 대대적으로 개선했습니다.
  - 패러그래프 세팅에 맞춰 `<p>` 태그에 동적으로 margin-bottom을 주입하는 `applyDynamicParagraphStyles` 헬퍼 함수를 추가했습니다.

### 3) 소스 클린업 및 배포 정교화
- **[deploy.py](file:///c:/project/media_server/deploy.py)**:
  - 원격지 파일 삭제 배열(`deprecated_files`)에 `static/js/viewer_epub.js`를 추가하고, `rm -rf` 명령을 수행하여 홈 서버 배포 시 원격지의 `static/js/viewer/epub` 폴더가 흔적 없이 제거되도록 자동화했습니다.
- **물리적 파일 삭제 (로컬)**:
  - `static/js/viewer_epub.js` 및 `static/js/viewer/epub/` 디렉터리 내의 14개 미사용 모듈 파일들을 완전히 영구 삭제 처리했습니다.

## 4. 해결 사항 및 최종 확인
- EPUB 도서 진입 시 본문 및 삽화 이미지가 깨지지 않고 부드럽게 렌더링되는 것을 확인했습니다.
- 가로 페이징 모드와 세로 연속 스크롤 모드 간 전환 시 렌더링에 왜곡이 발생하지 않는지 E2E 검증을 마쳤습니다.
