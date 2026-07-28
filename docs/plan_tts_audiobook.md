# 오디오북 TTS 및 가라오케 모드 구현 계획서

## 1. 개요
현재 미디어 서버의 텍스트 뷰어(EPUB, TXT)에 브라우저 내장 Web Speech API를 활용하여 고품질 텍스트 음성 변환(TTS) 기능을 추가합니다. 또한, 오디오가 재생될 때 현재 읽고 있는 텍스트를 시각적으로 강조해 주는 '가라오케 모드(하이라이팅)'를 함께 구현하여 완벽한 오디오북 경험을 제공하는 것을 목표로 합니다.

## 2. 요구 사항
- **구간 건너뛰기**: TTS 재생 중 특정 문장이나 앞뒤로 이동 가능해야 함.
- **음성 제어**: 재생 속도(배속) 및 목소리(피치/성별) 조절이 가능해야 함.
- **가라오케 모드**: 현재 읽고 있는 문장의 배경색을 하이라이트(형광펜) 처리해야 함.
- **자동 스크롤 및 페이지 넘김**: 읽고 있는 텍스트가 화면 밖으로 넘어가거나 챕터가 끝나면 자동으로 다음 청크를 로드하고 스크롤해야 함.

## 3. 기술 스택 및 아키텍처
- **음성 엔진**: 브라우저 내장 `window.speechSynthesis` (Web Speech API)
- **DOM 분석**: `TreeWalker` API (HTML 태그를 보존하면서 순수 TextNode만 추출)
- **하이라이팅**: `Range` 객체 및 `window.getSelection()` 또는 `CSS Custom Highlight API`

## 4. 구현 상세

### 4.1. Frontend UI (`media_viewer.html`)
- 뷰어의 오버레이 메뉴(`overlay-txt-controls-row`)에 TTS 전용 컨트롤 바 추가.
- 구성 요소:
  - `[재생/일시정지]`, `[정지]` 버튼
  - 배속 조절 드롭다운 (0.75x ~ 2.0x)
  - 보이스 선택 드롭다운 (시스템에 설치된 언어 및 목소리 목록 매핑)

### 4.2. TTS 컨트롤러 로직 (`static/js/viewer/tts_controller.js`)
- **텍스트 추출 및 매핑**:
  - `TreeWalker`를 이용해 현재 렌더링된 청크(`.txt-scroll-chunk`) 내부의 모든 `TextNode`를 순회.
  - 전체 문자열 길이와 각 TextNode가 위치한 시작/종료 인덱스(Offset)를 매핑한 배열 생성.
- **재생 추적 (`onboundary` 이벤트)**:
  - `speechSynthesisUtterance`의 `onboundary` 이벤트가 발생하면 반환되는 `charIndex`를 수신.
  - 매핑 배열을 이진 탐색하여 현재 `charIndex`가 속한 정확한 DOM TextNode를 탐색.
- **가라오케 하이라이팅**:
  - 탐색된 TextNode의 문장 범위(시작점~마침표)에 `Range` 객체를 생성하고 하이라이트 클래스(`.tts-highlight`) 적용.
  - 이전 하이라이트는 제거하여 한 문장씩 부드럽게 색칠되도록 연출.

### 4.3. 뷰어 연동 (`static/js/viewer_txt.js`)
- 사용자가 스크롤을 내리거나 챕터를 넘기면 TTS 컨트롤러의 기준 DOM 컨텍스트를 업데이트.
- TTS가 현재 화면 바깥의 문장을 읽으려 할 때 `scrollIntoView()`를 호출하여 자동 스크롤 구현.
- 현재 청크(챕터)의 읽기가 끝나면, 다음 청크 데이터를 로드(`fetch`)하고 매핑을 갱신한 뒤 이어서 재생.

## 5. 한계점 및 향후 과제
- **모바일 백그라운드 재생 제약**: Web Speech API는 iOS Safari 및 Android Chrome에서 화면이 꺼지면 일시적으로 멈추거나 연속 재생이 불가능한 OS 정책적 한계가 존재합니다.
- **해결 방안 (Phase 2)**: 백그라운드 재생이 필수적인 완전한 오디오북 서비스로 넘어가려면, 차후 백엔드(Python)에서 직접 텍스트를 MP3로 변환(Edge-TTS 등)하여 스트리밍하는 방식으로 전환하거나 전용 앱(Native App) 래퍼를 씌워야 합니다.
