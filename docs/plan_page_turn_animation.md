# 페이지 넘김(Page Turn) 애니메이션 실험 — 기록 및 실전 반영 계획

> 상태: 파일럿 성공 (2026-08-29). 아직 프로덕션 코드에는 반영되지 않음. 완전히 분리된 실험 라우트로만 존재.

## 1. 배경 / 목표

기존 만화(zip/cbz) 뷰어는 페이지 전환 시 즉시 다음 이미지로 교체되는 방식(순간 전환)이다. 실제 책을 넘기는 것처럼
부드럽게 곡률(curl)과 그림자가 있는 페이지 전환 애니메이션을 실험적으로 붙여보는 것이 목표.

핵심 요구사항(대화에서 도출):
- 기존 뷰어 로직은 절대 건드리지 않는다 — 완전히 분리된 별도 기능으로 테스트.
- 이미지 기반(zip/cbz) 도서부터 시작.
- 진짜 "종이" 느낌이어야 한다 — 딱딱한 통짜 회전(나무판 느낌)은 실패로 간주.
- **2페이지 펼침(spread) 모드가 핵심.** 책을 넘기는 경험은 좌/우 또는 우/좌로 펼친 종이가 넘어가는 것이지,
  1장짜리 단일 페이지 회전은 그 경험을 제대로 전달하지 못한다는 게 최종 판단.

## 2. 시행착오 기록

### 2-1. 1차 시도: 커스텀 CSS `rotateY` 플립 (폐기)
페이지 전체를 하나의 평면으로 보고 `perspective` + `rotateY`로 회전시키는 방식. 그림자 오버레이도 얹었지만,
페이지 전체가 곡률 없이 통짜로 회전하다 보니 **"나무판을 넘기는 것 같다"**는 평가를 받고 폐기.
곡률이 있으려면 넘어가는 가장자리부터 점진적으로 휘는 형태(스트립 워프 또는 실제 곡면 렌더링)가 필요하다는 결론.

### 2-2. 2차 시도: 오픈소스 라이브러리 도입 (채택)
직접 canvas 워프를 구현하는 대신, 검증된 오픈소스를 먼저 붙여서 "우리가 원하는 결과가 이거 맞는지"부터 확인하는
전략을 취함. 결과가 좋았고, 이후 세부 조정도 라이브러리 설정값으로 대부분 해결됐기 때문에 직접 구현(캔버스 스트립 워프)은
현재로선 불필요하다고 판단.

**"종이처럼 잘된다. 훨씬 부드럽네"** — 라이브러리 도입 직후 사용자 평가.

### 2-3. 버그 1: 의도치 않은 스프레드(2페이지) 모드
`minWidth`/`maxWidth`를 좁게 잡아뒀더니 컨테이너 폭이 우연히 임계값(`2×minWidth`)을 넘어서면서 두 장의 서로 다른
페이지 이미지가 나란히 붙어버림. 처음엔 "버그"로 보고 강제로 단일 페이지 모드로 고정했으나, 이후 대화에서
이 스프레드 동작 자체가 오히려 목표였다는 게 밝혀짐 (§2-5 참고).

### 2-4. 버그 2: `minWidth: 4000` 오용으로 인한 렌더링 붕괴
스프레드를 막으려고 `minWidth`를 4000px로 임의로 키웠는데, 이 값은 단순 판정 임계값이 아니라
**라이브러리가 컨테이너 요소의 CSS `min-width`로 그대로 적용하는 실제 레이아웃 값**이었다. 그 결과 브라우저를
아무리 축소해도(25% 줌까지) 책이 4000px 폭으로 고정되어 화면에 전혀 들어오지 않는 문제가 발생.

**교훈**: `minWidth`/`maxWidth`는 (1) 스프레드⇄단일 페이지 전환 임계값이면서 (2) 동시에 실제 DOM에 적용되는
CSS 값이다. 두 역할을 분리해서 생각하면 안 되고, 항상 실제 화면에 그대로 적용된다는 전제로 값을 잡아야 한다.

### 2-5. 방향 재검토: 단일 페이지 → 2페이지 스프레드로 전환
파일럿을 눈으로 확인한 뒤 사용자가 재고: *"페이지 넘김은 2장보기에서 지원되야 하는게 맞아. 1장일때는 의미가 없는거
같네. (인간의 경험상 책을넘긴다 -> 좌,우 또는 우,좌로 종이를 넘기는 경험)"*

→ §2-3에서 "버그"로 취급했던 스프레드 동작을 다시 정식으로 채택. `showCover: true`로 설정해 첫 페이지는
표지처럼 단독으로 열리고, 이후부터 좌/우 스프레드로 넘어가는 실제 책 구조를 흉내냄.

### 2-6. 버그 3: 뷰포트 세로 방향 미고려
컨테이너 폭을 `vw` 기준으로만 잡다 보니, 세로로 짧은 화면(브라우저 줌 아웃 등)에서 세로로 넘치는 문제가 발생.
스프레드 모드와 단일 페이지 모드는 폭 대비 높이 계산식이 다르기 때문에(스프레드가 훨씬 납작함), CSS `vw`/`vh`
조합만으로는 두 모드를 동시에 안전하게 커버할 수 없었음.

**해결**: JS에서 두 모드 각각의 예상 높이를 직접 계산해 실제 뷰포트(`innerWidth`/`innerHeight`)에 맞는 쪽을
선택하고, 컨테이너 폭을 인라인 스타일로 강제 지정. 리사이즈 시 재계산 + `pageFlip.update()` 호출.

## 3. 최종 파일럿 구조 (현재 코드)

완전히 분리된 실험 라우트로만 존재하며, 프로덕션 뷰어 코드(`static/js/viewer*.js`, `static/js/viewer/*.js`)는
**전혀 수정하지 않았다.**

```
api/routes/experimental_routes.py     # 신규 블루프린트, /experimental/page-turn 라우트 1개, @login_required
api/__init__.py                       # experimental_bp 등록 (추가만 함, 기존 등록부는 미변경)
templates/experimental_page_turn.html # 완전 독립 페이지 (인라인 CSS/JS, 프로덕션 뷰어 코드 미참조)
static/lib/page-flip.min.js           # 벤더링한 오픈소스 라이브러리 (아래 §4 참고)
```

기존 코드에서 재사용한 것은 **읽기 전용 API 2개**뿐이다:
- `GET /api/media/books/<book_id>/info?type=<db_type>` — `total_pages` 조회
- `GET /api/media/stream?book_id=<id>&page_idx=<n>&db_type=<db_type>` — 페이지 이미지 서빙

### 3-1. 테스트 방법
1. 로그인 상태에서 `/experimental/page-turn` 접속.
2. 이미지 기반(zip/cbz) 도서의 `book_id`와 `db_type`(general/adult)을 입력, 필요시 RTL 체크.
3. "열기" 클릭 → 화면 크기에 따라 자동으로 스프레드(넓은 화면) 또는 단일 페이지(좁은 화면) 모드로 렌더링.
4. 좌우 클릭/드래그/스와이프/화살표 키/하단 버튼으로 페이지 넘김 테스트.

### 3-2. 레이아웃 계산 핵심 (`templates/experimental_page_turn.html`)
```js
// 단일 페이지 기준 종횡비 (width:height). 실제 px가 아니라 비율로만 쓰인다.
var PAGE_W = 560;
var PAGE_H = 800;
var PAGE_ASPECT = PAGE_H / PAGE_W; // 1.4286
var MIN_PAGE_W = 340; // St.PageFlip settings.minWidth 와 반드시 일치시킬 것
var MAX_PAGE_W = 700; // St.PageFlip settings.maxWidth 와 반드시 일치시킬 것

function computeContainerWidth() {
  var availW = window.innerWidth * 0.94;
  var availH = (window.innerHeight - 70) * 0.9; // HUD/태그 여백 대략 제외

  var spreadWidth = Math.min(availW, 2 * (availH / PAGE_ASPECT));
  var spreadPageWidth = spreadWidth / 2;

  if (spreadPageWidth >= MIN_PAGE_W) {
    return Math.min(spreadWidth, 2 * MAX_PAGE_W);
  }
  var portraitWidth = Math.min(availW, availH / PAGE_ASPECT);
  return Math.min(portraitWidth, MAX_PAGE_W);
}

function applyLayout() {
  elBookContainer.style.width = computeContainerWidth() + 'px';
  if (pageFlip) pageFlip.update();
}
```

`MIN_PAGE_W`/`MAX_PAGE_W`는 레이아웃 계산과 `St.PageFlip` 생성자 설정(`minWidth`/`maxWidth`)에 **동일한 상수를
공유**해서 쓴다. 둘이 어긋나면 §2-3~2-4 버그가 재발한다.

### 3-3. PageFlip 초기화
```js
pageFlip = new St.PageFlip(document.getElementById('book'), {
  width: PAGE_W,
  height: PAGE_H,
  size: 'stretch',
  minWidth: MIN_PAGE_W,
  maxWidth: MAX_PAGE_W,
  minHeight: MIN_PAGE_W * PAGE_ASPECT,
  maxHeight: MAX_PAGE_W * PAGE_ASPECT,
  maxShadowOpacity: 0.55,
  showCover: true,       // 첫 페이지는 표지로 단독 표시
  usePortrait: true,     // 좁은 화면에서는 단일 페이지로 자동 폴백
  mobileScrollSupport: false,
  swipeDistance: 20
});
pageFlip.on('flip', function (e) { updateHud(e.data); });
pageFlip.loadFromImages(urls);
```

### 3-4. RTL(만화 우→좌) 처리 — 임시방편, 검증 안 됨
라이브러리에 RTL 옵션이 내장되어 있지 않아서, 이미지 URL 배열 자체를 `reverse()`해서 넣는 방식으로 우회했다.
페이지 번호 표시는 `totalPages - internalIdx`로 되돌려서 실제 book_id 상의 페이지 번호와 맞춘다.
**이 방식은 실제 읽기 진행률(reading_progress) 저장/북마크와는 전혀 연동되지 않은 임시 코드**이므로,
실전 반영 시 반드시 재설계 필요 (§5 참고).

## 4. 오픈소스 라이브러리: page-flip

- 패키지: [`page-flip`](https://www.npmjs.com/package/page-flip) (npm), StPageFlip의 유지보수 포크
- 원저장소: https://github.com/Nodlik/StPageFlip
- 라이선스: **MIT**
- 버전: 2.0.7 (2026-08-29 기준 vendoring)
- 벤더링 위치: `static/lib/page-flip.min.js` (44KB, 의존성 없음, UMD 빌드 → 전역 `window.St.PageFlip`)
- 조달 방법: `npm pack page-flip` 후 `dist/js/page-flip.browser.js`를 그대로 복사 (별도 빌드 과정 없음)
- 특징: canvas 기반 실시간 곡률 렌더링 + 그림자, 마우스 드래그/터치 스와이프/클릭 넘김 내장, 스프레드⇄단일
  페이지 자동 전환(`usePortrait`), 표지 단독 표시(`showCover`)

버전 업데이트가 필요해지면 같은 방식(`npm pack page-flip@<version>` → `dist/js/page-flip.browser.js` 교체)으로
갱신하면 된다. `package.json`에 정식 의존성으로 등록하지 않고 vendoring한 이유는 이 프로젝트가 프론트엔드 빌드
파이프라인(webpack/vite 등) 없이 정적 파일을 직접 서빙하는 구조이기 때문 — 기존 `static/lib/Sortable.min.js`,
`static/lib/font-awesome/`도 동일한 방식.

## 5. 실제 코드(프로덕션 뷰어)에 반영 시 고려사항

### 5-1. 결정이 필요한 선택지 (사용자 확인 없이 임의로 정하지 말 것)
- **통합 방식**: 지금처럼 완전히 분리된 별도 라우트/모드로 남길지, 기존 `viewer_comic.js` / `static/js/viewer/*`
  안에 설정 토글(예: "페이지 넘김 애니메이션 사용" on/off)로 흡수할지.
- **기본값**: 새 기능을 기본 ON으로 할지, 옵트인(설정에서 켜야 함)으로 할지. 기존 순간 전환 방식과 완전히
  대체할지, 병행 옵션으로 둘지.
- **적용 범위**: zip/cbz(이미지 기반)에만 적용할지, 추후 EPUB/TXT 페이지네이션 뷰어에도 확장할지
  (`project_epub_core_reprioritization` 메모 참고 — EPUB/뷰어 튜닝은 이미 우선순위 논의 중인 영역이라 이 실험과
  충돌하지 않게 조율 필요).
- **모바일 처리**: `mobileScrollSupport: false`로 꺼뒀는데, 실전에서는 세로 스크롤형 만화(웹툰류)와 충돌 여부
  확인 필요 — 웹툰은애초에 페이지 넘김 개념이 아니라 이 기능 대상에서 제외해야 함.
- **분할 보기(split spread) 기능과의 관계**: 기존 뷰어에는 이미 "가상 절반 페이지" 분할 보기 기능이 있음
  (`comicSplitSpread` 관련 함수들, `project_page_turn_experiment_pilot` 메모의 관련 항목 참고). page-flip의
  스프레드 모드와 기존 split-spread 기능이 개념적으로 겹치거나 충돌할 수 있으므로, 두 기능을 어떻게 공존시킬지
  결정 필요.

### 5-2. 기술적으로 반드시 처리해야 하는 것
- **RTL 재설계**: URL 배열 반전 방식은 폐기하고, 기존 `getComicReadingDirection()` /
  `toggleComicReadingDirection()` 설정과 연동되는 정식 구현 필요. 페이지 번호 ↔ 실제 book_id 페이지 매핑을
  명확히 분리해서 다뤄야 함 (읽기 진행률 저장 시 실제 book_id 페이지 인덱스를 써야지, 화면 표시용 반전 인덱스를
  쓰면 안 됨).
- **읽기 진행률(progress) 연동**: 현재 파일럿은 진행률을 전혀 저장하지 않음. `saveProgress()` 계열 기존 로직과
  연결 필요 — `pageFlip.on('flip', ...)` 콜백에서 훅.
- **프리로드/캐시 전략**: `loadFromImages()`는 전체 페이지 URL 배열을 한 번에 받지만, 라이브러리 내부적으로
  각 페이지를 `new Image()`로 지연 로드한다. 대용량 도서(수백 페이지)에서 초기 로드/메모리 사용량을 실측 확인
  필요. 기존 뷰어의 blob 캐시 맵(`blobCacheMap`, `getWholePageObjectUrl`) 방식과 통합할지, page-flip이
  자체적으로 처리하게 둘지 결정.
- **이미지 비율이 페이지마다 다른 경우**: `width`/`height` 설정은 고정 종횡비를 가정한다. 표지나 삽입 페이지가
  다른 비율이면 레터박스/크롭이 어떻게 보이는지 확인 필요.
- **다크/라이트 테마 연동**: 지금은 다크 배경 고정. 기존 뷰어의 테마 설정과 맞출지 결정.
- **에러 처리**: 이미지 로드 실패(404, 네트워크 오류) 시 page-flip 자체 로더 스피너만 표시됨 — 기존 뷰어의
  `showViewerError` 같은 사용자 피드백과 통일 필요.
- **접근성/키보드 포커스**: 현재 화살표 키 핸들러가 전역(`window`)에 붙어 있음 — 실전에서는 다른 단축키와
  충돌하지 않는지 확인.

### 5-3. 성능/검증 체크리스트 (다음 세션에서 점검)
- [ ] 190페이지급 대용량 만화에서 초기 로드 시간 및 메모리 사용량 실측
- [ ] GDrive/rclone 마운트 기반 원격 스토리지 환경에서의 로드 지연 확인 (`project_gdrive_rclone_majority_userbase`
      메모 참고 — 이 프로젝트 사용자 대다수가 rclone 마운트 GDrive를 쓰므로 필수 점검)
- [ ] 모바일 실기기 터치 스와이프 동작 확인 (현재는 데스크톱 브라우저에서만 검증됨)
- [ ] 세로가 매우 짧은 화면(가로 모드 태블릿, 저해상도 노트북)에서 레이아웃 재확인
- [ ] 표지가 없는(모든 페이지가 동일 비중인) 만화에서 `showCover: true`가 어색하지 않은지 확인
- [ ] RTL 정식 구현 후 페이지 번호/진행률 정합성 재검증
- [ ] 기존 split-spread 기능과의 공존/충돌 여부 확인
- [ ] 라이선스 고지 — MIT 라이선스 원문을 프로젝트 내 어딘가(예: `docs/` 또는 `THIRD_PARTY_LICENSES`)에
      명시할지 결정 (현재는 미고지 상태)

## 6. 관련 메모
- `project_page_turn_experiment_pilot` (auto-memory) — 이 문서의 요약 버전, 세션 간 컨텍스트 유지용
- `project_comic_viewer_range_serving_optimization` — 기존 만화 뷰어 로딩 최적화 이력
- `project_epub_core_reprioritization` — 뷰어 튜닝 전반의 우선순위 논의
