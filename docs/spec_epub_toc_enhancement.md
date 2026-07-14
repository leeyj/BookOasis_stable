---
title: "EPUB 목차 추출 및 뷰어 이동 기능 고도화 계획"
project: "BookOasis"
category: "spec"
date: 2026-07-14
tags: [spec, design, epub, toc]
---

# EPUB 목차 추출 및 뷰어 이동 기능 고도화 계획

본 문서는 BookOasis 웹 서비스에서 EPUB 파일 파싱 시 내장된 목차 정보를 정밀하게 추출하고, 이를 통합 뷰어 상에 사용자가 즉각 챕터로 건너뛸 수 있도록 목차 이동 인터페이스를 구축하는 고도화 개발 계획서입니다.

---

## 1. 목차 추출 백엔드 고도화 설계
현재 EPUB 변환 백엔드(`services/stream_service.py`)는 본문 HTML의 `<h1~h6>` 태그를 감지하여 챕터명을 유추하는 단순 방식을 사용하고 있습니다. 이를 보다 정밀하고 견고한 표준 EPUB 목차 추출 방식으로 개선합니다.

### A. EPUB 2/3 표준 목차 탐색
EPUB 스펙에 따라 다음 순서로 목차 메타데이터 파일을 탐색하여 파싱합니다.
1. **EPUB 3 표준 (Navigation Document)**:
   - OPF 파일 내 `<item properties="nav" ...>` 속성을 가진 XHTML 파일을 찾고, 내부의 `<nav xpath:type="toc">` 내 `<a>` 태그 목록을 추출합니다.
2. **EPUB 2 표준 (NCX 파일)**:
   - OPF 파일의 `<spine toc="ncx_id">`를 참조하거나 manifest에서 `application/x-dtbncx+xml` 미디어 타입을 가리키는 `.ncx` 파일을 로드합니다.
   - 내부의 `<navMap>` 트리 구조 하위 `<navPoint>` 요소의 `<navLabel><text>` 및 `<content src="...">` 속성을 재귀적으로 파싱하여 트리형 목차를 완성합니다.

### B. 백엔드 API 포맷 확장
`/api/media/epub` 응답 구조에 계층 구조가 유지된 목차 데이터 배열을 신설합니다.
```json
{
  "title": "책 제목",
  "chapters": [
    { "title": "1장. 프롤로그", "content": "..." },
    { "title": "2장. 모험의 시작", "content": "..." }
  ],
  "toc": [
    { "title": "1장. 프롤로그", "chapter_idx": 0, "anchor": "" },
    { "title": "2장. 모험의 시작", "chapter_idx": 1, "anchor": "" },
    {
      "title": "2장-1. 첫 번째 동료",
      "chapter_idx": 1,
      "anchor": "section-1-1"
    }
  ]
}
```

---

## 2. 프론트엔드 목차 UI/UX 설계 (`viewer_txt.js`)
기존의 소설/TXT 통합 뷰어를 수정하여 EPUB 파일 로드 시에만 목차 이동 패널을 활성화시킵니다.

### A. 목차 이동 트리거 추가
- 뷰어 상단 제어바에 목차 보기 토글 버튼(아이콘: `fa-list` 또는 `fa-bars-staggered`)을 배치합니다.
- 클릭 시 화면 좌측 또는 우측에 슬라이드 인(Slide-in) 형태로 사이드 목차 리스트바가 노출되도록 마크업과 CSS를 보강합니다.

### B. 챕터 점프 내비게이션
- 목차 목록의 항목 클릭 시 해당 항목이 매핑된 `chapter_idx`로 뷰어의 활성 페이지를 변경합니다:
  ```javascript
  function jumpToEpubChapter(chapterIdx, anchor = '') {
    currentChunkIdx = chapterIdx;
    renderCurrentChunk(true); // 본문 영역 렌더링
    
    // 특정 앵커(ID)가 지정되어 있는 경우 부드러운 스크롤 이동
    if (anchor) {
      const targetEl = document.getElementById(anchor);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth' });
      }
    }
  }
  ```

---

## 3. 마이그레이션 및 하위 호환성
- **TXT/EPUB 공용**: TXT 파일의 경우 목차가 기본적으로 존재하지 않으므로, 기존의 청크 분할 단위를 기준으로 임의의 `청크 1`, `청크 2`와 같은 형태로 자동 생성하여 동일한 목차 UI 계약을 준수하도록 유연하게 구현합니다.
- **저장소 로드**: 목차를 타고 이동할 때마다 `localStorage` 및 백엔드 진척도 API에 현재 읽고 있는 챕터 위치와 CFI 인덱스를 즉각 기록하여 중단 후 재독 시 완벽히 복원되도록 처리합니다.
