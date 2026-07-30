---
title: Walkthrough - i18n_dynamic_translation_system
project: BookOasis
category: history
date: 2026-06-30
type: walkthrough
---
# Walkthrough: i18n 동적 다국어 감지 및 로그인/메인 연동 완료

BookOasis의 글로벌 유저 확보를 위해 백엔드 JSON 언어팩 스캔 API 및 프론트엔드 다국어 번역 매니저(`i18n.js`)를 신설하고, 로그인 화면과 메인 사이드바/헤더/설정 탭에 다국어 동적 드롭다운을 성공적으로 이식하였습니다.

## 작업 상세

### 1. 동적 언어팩 감지 API 신설
- [utils/i18n_helper.py](file:///c:/project/media_server/utils/i18n_helper.py)를 구현하여 `static/i18n/*.json` 내의 `_meta.lang_name` 속성을 바탕으로 사용 가능한 다국어 번역팩 리스트를 탐색하도록 연동했습니다.
- [api/auth.py](file:///C:/project/media_server/api/auth.py) 마지막 라인에 `/api/i18n/languages` 공용 API 라우트를 바인딩하고, 세션 보안 검증 필터에서 예외 통과하도록 처리했습니다.

### 2. 프론트엔드 다국어 매니저 제작 ([static/js/i18n.js](file:///c:/project/media_server/static/js/i18n.js))
- 브라우저 기본 언어 및 `localStorage` 영구 설정을 캐싱하는 기능을 빌드했습니다.
- `t(key, variables)`: 중첩 번역 키 및 변수 보간 대치 기능 제공.
- `translateDOM(root)`: `data-i18n`(텍스트), `data-i18n-placeholder`(플레이스홀더), `data-i18n-title`(도움말)을 스캔해 자동 변환 적용.
- `renderLanguageSelector(container)`: 동적 셀렉터 엘리먼트를 빌드하고 변경 시 실시간 페이지 텍스트 재번역 이벤트 연결.

### 3. 로그인 및 메인 템플릿 마크업 전환
- [templates/login.html](file:///c:/project/media_server/templates/login.html): 우측 상단 언어 선택기 배치 및 `data-i18n` 속성 부여.
- [tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html): 좌측 사이드바 카테고리 명칭, 정렬 및 필터 단추 도움말, 검색 플레이스홀더, 일반/성인 토글 영역 다국어 속성 매핑 완료.
- [library_settings.html](file:///c:/project/media_server/templates/components/views/library_settings.html): 일반 설정 메뉴에 `#settings-i18n-container` 다국어 드롭다운 폼 바인딩 및 탭 전환 버튼, 스캔/플러그인/About 정보 카드의 정적 라벨 다국어 매핑 확장.
- [index.html](file:///c:/project/media_server/templates/index.html): `i18n.js` 로드 및 `DOMContentLoaded` 시점에 DOM 번역 및 설정 드롭다운 렌더링 호출 연동.

### 4. 초기 번역 사전 제공
- 한국어 사전(`ko.json`), 영어 사전(`en.json`), 그리고 동적 감지 검증용 일본어 사전(`ja.json`)을 구축하여 코드 수정 없이 언어팩 파일만 던지면 즉시 자동 스캔 및 번역 적용되는 확장성을 완벽히 확보하였습니다.
