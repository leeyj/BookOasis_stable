# 테마 외부화(플러그인 커스텀 테마 등록) 작업 인수인계

작성일: 2026-09-02 (세션 종료 시점 스냅샷) / 갱신: 2026-09-02 2차 세션

## 0-1. 2차 세션 진행 요약 (다음 세션은 여기부터 읽을 것)

4번 섹션의 A(CSS 파일 자체 룰의 패널 배경)와 B(시그니처 퍼플 리터럴)를 전부 처리 완료했다.
추가로 처리 도중 **핸드오버에 기록되지 않았던 새 발견**이 있었다:

- **`style.css`/`tab_media_library_viewer.css` 자체 룰 바디의 일반 텍스트색 하드코딩**
  (`#fff`/`#ffffff`/`#f8fafc`/`#f1f5f9`/`#e2e8f0` → text-primary, `#94a3b8`/`#cbd5e1`/`#64748b`
  → text-muted) 약 119곳. 1차 세션은 템플릿/JS의 인라인 `style=`만 훑었고 이 두 CSS 파일
  "자체 룰"은 놓치고 있었다. 사용자 확인 후 이번 세션에서 전부 치환 완료.
- **⚠️ 함정(3번 항목) 사례 추가 발견 및 수정**: 다음 5곳이 "불투명 accent 배경 + 잘못된
  텍스트색(`var(--app-text-primary)` 또는 리터럴 `#fff`/`white`)" 조합이었다 — 전부
  `var(--app-accent-contrast)`로 재수정함:
  - `static/js/settings/reports.js`의 페이지네이션 활성 버튼
  - `templates/components/media_viewer.html`의 `viewer-next-episode-confirm-btn`
  - `static/css/tab_media_library_viewer.css`의 `.filter-chip-item.active`, `.btn-filter-apply`,
    `.seekbar-tooltip`, `.btn-nav:hover`
  - `static/css/style.css`의 `.btn-resume-series`, `.btn-nav-arrow:hover`
  - 이 패턴은 새 하드코딩을 변수로 치환할 때마다 재발할 수 있는 종류의 버그이니, 앞으로도
    "불투명 accent 배경 위 텍스트인가?"를 항상 먼저 확인할 것.
- **결정 사항**: `login.css`(로그인 화면)/`tv.css`(TV 모드)는 사용자가 명시적으로 **테마
  외부화 스코프에서 계속 제외**하기로 결정함 (독립 페이지로 유지). 4번 섹션의 D 항목은
  이제 "제외 확정"으로 종료.
- 남은 것: `templates/index.html`의 의도적 예외 4곳(변경 없음, 계속 유지), `login.css`/`tv.css`
  (스코프 제외 확정), **E(8개 테마 시각 회귀 테스트)는 여전히 미착수** — 다음 세션 최우선 순위.

## 0-2. 2차 세션 실배포 테스트 후 버그 리포트 + 수정 (같은 세션 이어서)

사용자가 위 작업을 실배포해서 테스트: 대시보드/도서상세/설정 등 테마 전환은 정상, **단 e-paper
테마에서 설정 탭의 "현재 선택된" 활성 버튼 글자가 안 보임**을 확인. 원인 조사 결과 훨씬 넓은
범위의 "불투명 배경 + 잘못된 텍스트색" 버그가 발견되어 전부 수정함:

- **직접 원인**: `[data-app-theme="epaper"] .settings-tab-btn.active { background: #000000; color:
  var(--app-text-primary); }` — epaper의 `--app-text-primary`가 `#000000`이라 검정 배경에 검정
  글자. `var(--app-accent-contrast)`(epaper에서 `#ffffff`)로 수정.
- **같은 파일에서 동일 패턴 6곳 추가 발견 및 수정**: epaper `.sidebar-menu .menu-item.active`(+
  자식 선택자), light/sepia/aquamarine/ironman의 `.settings-tab-btn.active` — 전부 테마별
  `!important` 오버라이드 블록으로, 1차 세션의 "색상 하드코딩 → 변수" 일괄 치환 당시 "이 배경이
  불투명 accent/고정색 채움인가"를 확인 안 하고 넘어간 영역. 전부 `var(--app-accent-contrast)`로
  수정.
- **더 넓은 스캔 결과**: "고정 리터럴 배경(테마 무관) + `var(--app-text-primary)` 텍스트" 조합을
  `static/css/*.css` 룰 바디 + `templates/**/*.html`, `static/js/**/*.js`의 인라인 `style=`
  전체에서 재스캔 → 아래 15곳 추가 발견 및 수정:
  - `style.css`: `.btn-settings-save`(#7c3aed 배경 → accent 다크변형+accent-contrast로 전환),
    `.ridi-link-btn`/`:hover`, `.btn-download`, `.btn-active-filter-reset:hover`,
    `.vol-grid-download-btn:hover` → 전부 고정 `#fff` 텍스트로
  - `tab_media_library_viewer.css`: `.overlay-close-btn:hover`, `.overlay-tab-btn.active`,
    `.overlay-select`, `.btn-overlay-fit.active`, `.btn-nav`, `.btn-txt-ctrl:hover`,
    `.txt-reader-theme-dark`/`-black` → 고정 `#fff`/`#f1f5f9` 텍스트로 (reader 프리셋은
    light/sepia/epaper/white 프리셋처럼 앱 테마와 무관한 고정 팔레트가 원래 의도였음)
  - `templates/components/modals/library_modal.html`의 경로 선택 버튼(`#a855f7` 배경) →
    `var(--app-accent)`+`var(--app-accent-contrast)` (진짜 accent였음)
  - `general_tab.html`(지금 스캔 버튼), `trash_tab.html`(DB 선택 select) → 고정 텍스트/
    `var(--app-input-bg)`로
  - `static/js/detail_render.js`의 추천 메타 적용 버튼(#7c3aed) → accent 다크변형 패턴
  - `static/js/settings/users.js`의 삭제/비번변경/비번초기화 버튼 3곳 → 고정 `#fff`
  - `static/js/tab_collections.js`의 모달 박스 3곳(`#1e293b` 고정) → `rgba(var(--app-panel-rgb),
    1)`로 아예 테마 추종하도록 전환 (텍스트는 그대로 `var(--app-text-primary)` 유지 — 배경을
    고쳤으므로 이제 맞음)
  - `static/js/viewer/plugin_prompt_modal.js`의 모달 박스(`#1e293b`)/입력창(`#0f172a`) →
    박스는 `rgba(var(--app-panel-rgb), 1)`, 입력창은 `var(--app-input-bg)`로 테마 추종 전환
- **⚠️ 새로운 설계 원칙 확정 (사용자 결정, 향후 계속 적용할 것)**: 오디오북 풀스크린 몰입형
  플레이어(`audio_player_modal.html`)와 만화/미디어 뷰어 모달(`media_viewer.html`의
  `.viewer-modal`/`.comic-loading-overlay` 등, `tab_media_library_viewer.css`에 정의)은
  **의도적으로 앱 테마와 무관하게 항상 어두운 "극장판" 배경**으로 설계된 영역이다. 사용자가
  "항상 어두운 채로 고정"을 선택함에 따라:
  - `audio_player_modal.html` 전체(33곳)의 `var(--app-text-primary)`→`#f1f5f9`,
    `var(--app-text-muted)`→`#94a3b8`로 고정 치환 완료 (이 파일은 `var(--app-panel-rgb)`/
    `var(--app-accent)`를 단 한 번도 안 쓰고 있었음 — 배경 전체가 원래 고정 팔레트 설계)
  - `media_viewer.html`의 `#viewer-common-close-btn`/`#viewer-next-episode-cancel-btn`
    (부모가 `.comic-loading-overlay`, 배경 고정 `rgba(9,13,22,0.92)`) → `#f1f5f9`로 고정
  - **앞으로 이 두 영역(오디오 플레이어, 만화/미디어 뷰어 모달) 안에 새 UI를 추가할 때는
    `var(--app-*)` 테마 변수를 쓰지 말고 고정 다크 팔레트(#f1f5f9 텍스트, #94a3b8 뮤트텍스트
    등)를 그대로 따를 것.** 반대로 `.viewer-padding-panel`처럼 이미 `rgba(var(--app-panel-rgb),
    X)`를 쓰는 하위 패널(뷰어 여백 설정 등)은 정상적으로 테마를 따라가야 하므로 그대로 둠 —
    "뷰어 모달 = 무조건 다크"가 아니라 "그 모달의 배경 자체가 고정 리터럴인 하위 요소만" 대상.
- 이 조사에서 확인된 것: 이런 종류의 버그(불투명/고정 배경 위에 실수로 테마 텍스트 변수를 쓴 것)는
  1차 세션의 일괄 치환 방식 자체의 구조적 위험이었다. 앞으로 유사 치환을 할 때는 항상 "이 배경이
  (a) 테마를 따라가는 배경인지 (b) 고정 리터럴/accent 배경인지"부터 확인하고, (b)라면 텍스트도
  그에 맞는 고정색 또는 `var(--app-accent-contrast)`를 쓸 것 — 3번 섹션의 "함정" 규칙을 이제
  이렇게 일반화해서 기억할 것.

## 0. 왜 이 작업을 시작했나

커뮤니티 요구사항 중 "플러그인이 자기 테마를 등록할 수 있게 해달라"는 게 있었다. 검토해보니
기술적으로 배관(plumbing) 자체는 쉬웠다 — `metadata_factory.py`의 `category_tab`/`dashboard_widget`
패턴(플러그인 클래스에 dict 속성 선언 → 코어가 `getattr`로 수집 → API로 프런트에 노출)을
그대로 재사용하면 됨.

**진짜 문제는 코어 UI 자체가 CSS 변수 기반이 아니었다는 것.** `data-app-theme` 테마 시스템은
존재했지만(`static/css/style.css`의 8개 테마 블록: purple/dark/light/sepia/blue/aquamarine/
ironman/epaper), 실제 색상은 템플릿/JS 곳곳에 인라인 `style="color: #fff"` 같은 식으로
하드코딩돼 있었다. 그래서 `light`/`sepia`/`epaper` 같은 밝은 테마는 `[style*="color: #fff"]`
같은 **문자열 부분일치 CSS 셀렉터로 인라인 스타일을 `!important` 강제 override**하는 방식으로
땜질돼 있었다 (예: `light`/`sepia`/`epaper` 3개 테마에서만 총 24줄의 이런 hack이 있었음).

플러그인이 변수 dict만 넘겨서 테마를 등록하게 하려면, "accent 변수 몇 개만 바꾸면 앱 전체가
일관되게 재도색된다"는 계약이 코어에서 실제로 성립해야 한다. 지금은 안 그렇다. 그래서
**"먼저 하드코딩을 걷어내서 기반을 다지고, 플러그인 테마 등록 설계는 그 다음에 다시 논의한다"**로
방향을 잡았다. 이 문서는 그 걷어내기 작업의 진행 상황이다.

## 1. 지금까지 확립된 매핑 규칙 (다음 세션에서 그대로 재사용할 것)

이 규칙들은 실제로 각 테마의 기존 `!important` override 값과 대조해서 **정확히 일치함을
검증한 뒤** 확정한 것들이다 (임의로 정한 게 아님). 새로 하드코딩을 발견하면 아래 표에 맞는
치환을 적용하면 된다.

| 패턴 | 치환 | 비고 |
|---|---|---|
| `color: #fff` / `#ffffff` / `#f8fafc` / `#f1f5f9` / `#e2e8f0` | `var(--app-text-primary)` | "밝은 배경 위 진한 텍스트" 계열. light/sepia/epaper override 값과 정확히 일치 확인됨 |
| `color: #94a3b8` / `#cbd5e1` / `#64748b` | `var(--app-text-muted)` | "보조/뮤트 텍스트" 계열 |
| `background: rgba(30, 41, 59, X)` 또는 `rgba(15, 23, 42, X)` (카드/패널 반투명 배경) | `rgba(var(--app-panel-rgb), X)` | X(알파값)는 원본 그대로 보존. **새 변수**, 8개 테마 전부에 이미 추가됨 |
| 위와 짝을 이루는 `border: ... rgba(255, 255, 255, X)` | `rgba(var(--app-panel-border-rgb), X)` | 마찬가지로 새 변수, 알파값 보존 |
| "시그니처 퍼플" CTA 그라디언트 `#a855f7 → #7c3aed`(또는 `#c084fc → #7c3aed`) | `linear-gradient(135deg, var(--app-accent) 0%, color-mix(in srgb, var(--app-accent) 70%, black) 100%)` | 진한 쪽은 `color-mix`로 자동 계산, 테마별로 값 안 정해도 됨 |
| 위 버튼의 `color: #fff`(글자색) | **`var(--app-accent-contrast)`** (⚠️ `var(--app-text-primary)` 아님!) | 아래 "함정" 섹션 참고 |
| 아이콘 강조색 `#a855f7` | `var(--app-accent)` | |
| 강조 수치/값 텍스트 `#c084fc` (더 밝은 톤) | `var(--app-accent-hover)` | 기존에 이미 "밝은 톤" 용도로 쓰이던 변수라 재사용 |
| `accent-color: #a855f7` (range/checkbox) | `accent-color: var(--app-accent)` | |
| 그라디언트/박스섀도의 나머지 rgba(168,85,247,X) 계열 | `color-mix(in srgb, var(--app-accent) X%, transparent)` | |

### ⚠️ 함정: `var(--app-accent-contrast)` vs `var(--app-text-primary)`

- **불투명(solid) accent 배경 위의 글자색** → 반드시 `var(--app-accent-contrast)` 사용.
  `dark` 테마의 accent(`#38bdf8`, 밝은 하늘색)와 `blue` 테마의 accent(`#64ffda`, 민트)는
  둘 다 매우 밝은 색이라 흰 글자를 얹으면 대비가 거의 안 나온다. 그래서 8개 테마 전부에
  `--app-accent-contrast` 변수를 새로 추가했음 (`dark`→`#0f172a`, `blue`→`#0a192f`,
  나머지는 `#ffffff`).
- **반투명 accent 틴트 위(예: hover 시 15~18% 알파로만 tint되는 배경)** → 배경이 대부분
  페이지 자체 배경색이라 `var(--app-text-primary)`를 써야 함. `--app-accent-contrast`를
  쓰면 dark/blue 테마에서 어두운 글자가 여전히 어두운 배경 위에 얹혀 안 보이게 됨.
  (`.btn-back-to-list:hover`, `permissions_tab.html`의 탭 버튼에서 실제로 이 실수를
  했다가 바로 고침 — `services/category_service.py` 관련 아님, CSS 얘기)
- 판단 기준: **"이 배경이 불투명 accent 단색 채움인가, 아니면 얇은 반투명 틴트인가"**로
  결정할 것.

## 2. 새로 추가된 CSS 변수 (8개 테마 전부, `static/css/style.css`)

기존에 있던 `--app-bg-main` / `--app-bg-card` / `--app-text-primary` / `--app-text-muted` /
`--app-accent` / `--app-accent-hover` / `--app-border` / `--app-border-light` /
`--app-input-bg` / `--app-shadow` / `--app-blur` 세트에 아래 3개를 추가했다:

- **`--app-panel-rgb`**: 카드/패널 반투명 배경의 RGB 채널 (알파 없이). `rgba(var(--app-panel-rgb), 0.X)`
  형태로 쓴다. 각 테마의 `--app-bg-card`와 같은 계열 색.
  - purple: `30, 41, 59` (원래 하드코딩 값 그대로, 무변화)
  - dark: `36, 36, 36` (기존엔 override가 아예 없어서 보라 틴트가 새고 있었음 — 이번에 실제로 고쳐진 것)
  - light/epaper: `255, 255, 255`
  - sepia: `244, 228, 193`
  - blue: `17, 34, 64`
  - aquamarine: `25, 58, 72`
  - ironman: `28, 25, 23`
- **`--app-panel-border-rgb`**: 위 패널의 테두리 RGB. 대부분 `255, 255, 255`(흰 반투명 유지),
  light `226, 232, 240` / sepia `230, 211, 173` / epaper `0, 0, 0`.
- **`--app-accent-contrast`**: 위 "함정" 섹션 참고. purple/light/sepia/aquamarine/ironman/epaper는
  `#ffffff`, dark는 `#0f172a`, blue는 `#0a192f`.

`epaper` 테마의 `--app-text-muted`도 `#222222` → `#000000`으로 값 조정했음 (기존 override가
강제로 순검정을 만들고 있었는데, 그 override를 지우면서 변수 자체를 맞춰 시각적 변화 없이 이관).

## 3. 이번 세션에서 완료한 것 (파일별)

### 3-1. 텍스트 색 하드코딩 제거
- 템플릿 25개 파일 (253곳) + JS 25개 파일 (141곳), 총 394곳
- 추가로 `#f8fafc`/`#f1f5f9`/`#e2e8f0` 46곳 (같은 규칙으로 추가 발견/수정)
- `light`/`sepia`/`epaper` 테마의 `[style*="color: #fff"]` 류 문자열-매칭 셀렉터 24줄 완전 제거
  (`static/css/style.css`)

### 3-2. 패널/카드 배경 하드코딩 제거
- 템플릿 16개 + JS 20개 파일의 인라인 `style="..."` 안 rgba(30,41,59)/rgba(15,23,42) →
  `rgba(var(--app-panel-rgb), X)`
- `light`/`sepia`/`epaper`의 `div[style*="background: rgba(...)"]` override 3블록 제거
- `.btn-back-to-list`, `.btn-read`, `.btn-submit`, `.btn-fit.active`, 토글 스위치 등
  **CSS 파일 자체(인라인 아님)** 룰 바디도 일부 전환함 — 단, 전수조사는 아님 (4번 섹션 참고)

### 3-3. `templates/index.html` 자체 버그 + 죽은 코드
- `body { background-color: #0f172a }`가 `data-app-theme`와 무관하게 고정 → 
  `var(--app-bg-main, #0f172a)`로 수정 (fallback을 넣은 이유: 이 인라인 `<style>`이
  `<head>`에 있고 `static/css/style.css`는 `{% include "components/tab_media_library.html" %}`
  안에서야 로드되므로, fallback 없이 그냥 `var()`만 쓰면 로드 전 잠깐 투명/흰 화면이 됨)
- `user_theme_color` Jinja 변수: 백엔드 어디서도 `render_template()`에 넘긴 적 없는 죽은 코드였음
  (실제로는 항상 `#a855f7` 상수로 동작 중이었음) → 삼중 `{{ user_theme_color|default(...) }}`
  참조를 제거하고 리터럴 값으로 단순화

### 3-4. CTA 버튼 계열 (accent 따라가도록)
- `.btn-read`(뷰어 이어보기/처음부터), `.btn-submit`, `.btn-fit.active`, 토글 스위치
  (`static/css/style.css`, `tab_media_library_viewer.css`)
- 인라인 버튼 5곳: `general_tab.html`, `my_settings_tab.html`, `plugins_tab.html`,
  `schedule_tab.html`, `viewer_tab.html`의 저장/스캔/샘플설치 버튼
- 이 과정에서 **실제 버그 발견**: 1차 텍스트색 일괄치환 때 이 버튼들의 `color: #fff`가
  `var(--app-text-primary)`로 잘못 치환돼 있었음 — epaper 테마는 `--app-text-primary`가
  검정인데 accent도 검정이라 **버튼 글자가 안 보이는 상태**였음. `--app-accent-contrast`로 재수정.

### 3-5. 설정 탭 아이콘 전체
- `templates/components/settings/*.html` 전 파일, `color: #a855f7`/`#c084fc`/
  `accent-color: #a855f7` 49곳 일괄 치환
- `about_tab.html`의 "BookOasis" 로고 워드마크(흰색→보라 그라디언트 텍스트)는 **의도적으로 제외**
  (브랜드 아이덴티티, 테마 무관하게 유지하는 게 맞다고 판단)

### 3-6. 사이드바 그룹/카테고리 아이콘
- `static/js/category/index.js`: 사이드바 추가(+)/그룹추가/컬렉션 북마크/핀 고정/스캔
  스피너 아이콘 등 하드코딩 제거
- **백엔드 근본 원인 발견 및 수정**: 그룹 색상을 고르는 UI 자체가 없어서, 모든 그룹이
  DB 스키마 기본값 `color TEXT DEFAULT '#a855f7'`를 그대로 갖고 있었음. 프런트 fallback만
  고쳐선 절대 해결 안 되는 문제였음.
  - `database.py`, `tools/db_schema_updater.py` 스키마 기본값 → `NULL`
  - `repositories/{sqlite,mariadb}/category_repository.py`의 `add_library_group()`
    기본 인자 → `color=None`
  - **기존에 이미 만들어진 그룹들**을 위한 1회성 백필 마이그레이션
    `_backfill_library_group_default_color()` 추가 (`database.py`, `_backfill_audiobook_last_listened_at`과
    동일한 자리/패턴). `color = '#a855f7'`인 행만 정확히 찾아 `NULL`로 되돌림 — 반복 실행 안전(idempotent).
    **다음 서버 기동 시 자동 실행됨.**

### 3-7. (테마와 별개) 뷰어 오버레이 드래그 핸들
- 커뮤니티 요청("뷰어 컨텍스트 메뉴를 옮길 수 있게")으로 `overlay-controls-panel`에 작은
  드래그 앵커 추가. `static/js/context_menu_manager.js`의 `enableMenuDrag()`를 범용화해서
  (flexbox로 auto-배치되던 요소도 첫 드래그 시점에 `position:fixed`로 스냅) 구현.
  테마 작업은 아니지만 같은 세션에 했고 CHANGELOG v2.5.4에 기록됨. 참고로만 남김.

## 4. 아직 안 된 것 (다음 세션 시작점) — ⚠️ A/B/D는 2차 세션에서 완료/확정됨, 아래는 1차 세션 종료 시점 스냅샷 그대로 보존 (0-1 참고)

아래는 세션 종료 시점에 실제로 grep 돌려서 확인한 **정확한 잔여 수치**다. 다음 세션에서
아래 명령을 다시 돌려서 최신 상태를 재확인하고 시작할 것:

```bash
# 리터럴 시그니처 퍼플(#a855f7/#c084fc)이 남은 파일과 개수
grep -rc '#a855f7\|#c084fc' static/js/*.js static/js/**/*.js templates/**/*.html templates/*.html static/css/*.css 2>/dev/null | grep -v ':0$'

# CSS 파일 "자체" 룰 바디(인라인 아님)에 남은 패널 배경 하드코딩
grep -rc 'rgba(30, 41, 59\|rgba(15, 23, 42' static/css/*.css | grep -v ':0$'
```

세션 종료 시점 결과:

**A. CSS 파일 자체(인라인 아님)의 패널 배경 하드코딩 — 미착수, 우선순위 1순위**
지금까지 손댄 건 전부 "템플릿/JS의 인라인 `style=` 속성"이었다. `style.css`/
`tab_media_library_viewer.css` **파일 안에 직접 정의된 CSS 룰**(다른 카드/모달/컴포넌트
스타일들)은 훑지 않았다.
- `static/css/style.css`: 27곳
- `static/css/tab_media_library_viewer.css`: 14곳
- `static/css/login.css`: 3곳 (별도 페이지, 우선순위 낮음)

**B. 시그니처 퍼플(`#a855f7`/`#c084fc`) 리터럴 — 22개 파일**
- `static/css/style.css`: 22곳
- `static/css/tab_media_library_viewer.css`: 15곳
- `templates/components/context_menus.html`: 9곳 (도서/카테고리 우클릭 메뉴 아이콘들)
- `templates/components/media_viewer.html`: 7곳
- `static/js/tab_collections.js`: 5곳
- `static/js/settings/reports.js`: 5곳
- `static/js/scheduler.js`: 4곳
- `static/js/plugin_custom_view.js`: 4곳
- `static/js/settings/plugins.js`: 3곳
- `static/js/detail/header_view.js`: 3곳
- `static/js/settings/queue.js`: 2곳
- `static/js/settings/permissions.js`: 2곳
- `static/js/metadata_search.js`: 2곳
- `static/css/login.css`: 2곳 (별도 페이지)
- 기타 소수 파일들

**C. `templates/index.html`에 남은 4곳 — 확인 완료, 의도적으로 그대로 둠**
`--color-accent`/`--color-accent-hover`/`--bg-glow-1`(배경 은은한 글로우 효과) +
콘솔 이스터에그 로그 1곳. 전부 "브랜드 아이덴티티/장식" 성격이라 테마 무관 유지가 맞다고
판단해서 손 안 댐. 새로 살펴볼 때 다시 건드리지 말 것.

**D. `login.css`/`tv.css` — 별도 페이지, 아예 미착수**
로그인 화면과 TV 모드는 이번 스코프에서 완전히 제외됨. 메인 앱과 톤이 달라도 되는
독립 페이지인지, 통일해야 하는지부터 사용자와 논의 필요.

**E. 시각 회귀 테스트 — 전혀 안 함**
8개 테마를 실제로 하나씩 켜서 페이지별로 눈으로 확인한 적이 없다. 지금까지의 변환은
전부 "override 값과 일치하는지 코드 레벨로 대조"하는 방식으로 검증했지, 렌더링 결과를
스크린샷으로 확인하진 않았다. `light`/`sepia`/`epaper`/`dark`/`blue`/`aquamarine`/
`ironman`/`epaper` 각각 최소 한 번씩은 메인 화면 + 설정 화면 + 뷰어를 띄워봐야 한다.

## 5. 지켜야 할 원칙/예외 (다시 결정하지 말고 그대로 따를 것)

- **브랜드 워드마크/로고**: 테마 무관하게 유지. (`about_tab.html`의 "BookOasis" 텍스트,
  `index.html`의 배경 글로우 효과 등)
- **범용 시맨틱 색**: 별점=노랑(`#eab308`), 삭제/위험=빨강(`#ef4444`/`#f87171`),
  Google Drive 아이콘=구글 블루(`#60a5fa`) 같은 건 테마 accent와 무관하게 유지. 이런 색은
  "브랜드 accent"가 아니라 "의미 고정 색"이라 변환 대상이 아님.
- **관리자가 명시적으로 커스터마이징한 값**은 절대 덮어쓰지 않는다. 항상 "커스터마이징
  안 됐을 때의 기본값"만 고친다 (3-6의 그룹 색 백필이 정확히 이 원칙으로 안전했던 이유 —
  애초에 그룹 색을 고르는 UI가 없어서 100% 기본값이었음을 먼저 확인하고 진행했음).
- **`experimental_page_turn.html`**: 격리된 실험 라우트(memory 참고: 페이지-플립 파일럿).
  자체 다크 팔레트가 하드코딩돼 있지만 의도된 격리이므로 이번 테마 작업 스코프에서 계속 제외.
- 새 인라인 `rgba(30,41,59,X)`/`rgba(15,23,42,X)`를 변환할 때 **알파값(X)은 항상 원본 그대로
  보존**할 것 (플랫하게 하나로 통일하지 않기로 결정했음 — 대신 `--app-panel-rgb`처럼 RGB만
  변수화하고 알파는 각 인스턴스가 이미 쓰던 값을 유지하는 `rgba(var(--x), X)` 패턴 사용).

## 6. 다음 세션 진행 순서 제안

1. ~~위 4번 섹션의 grep 명령으로 최신 잔여 현황 재확인~~ — 완료 (0-1 참고)
2. ~~A(CSS 파일 자체 룰 바디)부터 처리~~ — 완료
3. ~~B(나머지 22개 파일의 리터럴 퍼플)~~ — 완료 (템플릿/JS 전체 + style.css/
   tab_media_library_viewer.css 자체 룰까지, 텍스트색 하드코딩 119곳 포함)
4. ~~login.css/tv.css 스코프 포함 여부~~ — 사용자가 **제외(독립 유지)**로 확정
5. ~~E(8개 테마 시각 회귀 테스트)~~ — 완료. 사용자가 실배포 환경에서 8개 테마 전부 직접 확인,
   "매우 잘 된다"고 확정. epaper 버그(0-2 참고)까지 실제로 재배포해서 재확인 완료.
6. ~~플러그인 테마 등록 기능 설계~~ — **방향 전환 후 구현 완료 (2026-09-02 3차 세션)**.
   자세한 내용은 0-3 참고.

## 0-3. 3차 세션: "플러그인 테마 등록" → "테마 파일(YAML) 등록"으로 방향 전환 + 구현

원래 계획(6번 항목)은 플러그인 클래스에 `theme_manifest` 속성을 선언하는 방식이었으나,
사용자가 "테마 1개당 플러그인 1개는 비효율적"이라는 문제를 제기해 **설계를 전면 교체**했다:
플러그인(실행 코드)이 아니라 `themes/` 디렉토리에 놓는 순수 YAML 데이터 파일로 테마를
등록하는 방식. 코드를 실행하지 않는 데이터 파일이라 신뢰 경계가 오히려 더 단순해졌다
(화이트리스트 키 + 정규식 값 검증만으로 raw CSS 주입을 막음 — 플러그인 신뢰 문제 자체가
사라짐).

**사용자 결정 2가지 (재논의 불필요, 그대로 따를 것):**
- 테마 파일이 `themes/`에 있으면 관리자 승인/개별 토글 없이 **곧바로** 노출된다.
- 재적용은 **서버 재시작이 아니라 "재스캔" 버튼**으로 한다 (관리자 전용).

**구현된 것 (전부 완료, 미배포 상태 — 다음 세션은 실배포 테스트부터):**
- `services/custom_theme_service.py` — `themes/*.yaml`/`*.yml` 스캔·검증·CSS 생성.
  화이트리스트는 8개 내장 테마가 실제로 쓰는 15개 `--app-*` 변수(`app-shadow`/`app-blur`는
  box-shadow/filter 문법이 열려있어 의도적으로 제외 — 스펙에서 아예 미지원). 하나라도
  검증 실패하면 그 파일 전체를 거부(부분 적용 금지). `id`가 내장 8개 테마와 겹치면 거부.
  값 검증: 13개는 hex색(`^#[0-9a-fA-F]{3,8}$`), `app-panel-rgb`/`app-panel-border-rgb`는
  `R, G, B`(0-255) 트리플릿만 허용.
- `themes/README.md` — 사용자용 작성 가이드 (스펙 표, 각 변수 역할 설명, 재스캔 안내)
- `themes/example.yaml.sample` — 예시 템플릿 (`.yaml`로 안 끝나서 자동 로드 안 됨, 참고용)
- API 3개, 전부 `api/routes/settings_routes.py`에 추가 (기존 `settings_bp` 재사용, 새 블루프린트
  안 만듦):
  - `GET /api/media/settings/custom-themes` (`@login_required`) — id/label 목록
  - `GET /api/media/settings/custom-themes.css` (`@login_required`) — 검증 통과분을
    `[data-app-theme="id"] { --app-x: value; }` CSS로 렌더링, `Cache-Control: no-cache`
  - `POST /api/media/settings/custom-themes/rescan` (`@admin_required`) — 재스캔 트리거,
    `{loaded_count, rejected: [{file, reason}]}` 반환
- `templates/components/tab_media_library.html`에 위 CSS 라우트를 `<link>` 태그로 추가
  (기존 `style.css`/`tab_media_library_viewer.css`와 같은 자리, 같은 패턴)
- `static/js/api.js`에 `fetchCustomThemes()` / `rescanCustomThemes()` 추가
- `static/js/settings/general.js`:
  - `populateCustomThemeOptions()` — `applySettingsToUI()`에서 호출, `my-setting-dashboard-theme`
    select에 `<option>` 동적 추가 (label은 **반드시 textContent로만** 넣음, innerHTML 금지 —
    사용자가 작성한 문자열이라 XSS 방지 원칙 적용)
  - `rescanCustomThemesUi()` — 재스캔 버튼 클릭 핸들러, 결과(로드/거부 개수+사유)를
    `#custom-theme-rescan-result`에 표시
- `templates/components/settings/general_tab.html`에 "커스텀 테마" 카드 추가 (재스캔 버튼 +
  결과 표시 영역) — 이 탭 전체가 이미 관리자 전용으로 비활성화되는 폼(`settings-general-form`)
  안이라 별도 권한 체크 코드 불필요

**검증 완료 (Python 스크립트로):**
- 정상 테마 파일 로드 성공, CSS 생성 정확함
- `id: purple`(내장 테마 이름 충돌) → 거부 확인
- 화이트리스트에 없는 키(`raw-css-injection: "url(javascript:alert(1))"`) → 거부 확인
- `node --check`로 `api.js`/`general.js` 문법 오류 없음 확인, Flask 앱 임포트 체인 정상

**다음 세션에서 할 것:**
- 사용자가 직접 실배포 환경에서 테스트 (요청에 따라 이번 세션은 브라우저 구동 테스트 생략함):
  1. `themes/example.yaml.sample`을 `.yaml`로 복사 → 재스캔 → "내 설정" 드롭다운에 뜨는지
  2. 선택 시 실제로 해당 색상이 적용되는지 (특히 `app-accent-contrast` 직접 계산해서 넣게
     했으므로, 사용자가 대비 계산을 틀리게 넣으면 그 테마 안에서 이 세션에서 고친 것과
     동일한 "불투명 accent 배경 위 텍스트 안 보임" 버그가 재현될 수 있음 — 이건 사용자의
     테마 파일 책임 영역이므로 README에 이미 강조해뒀음)
  3. 화이트리스트/정규식 위반 파일을 실제로 넣고 재스캔 결과에 사유가 잘 뜨는지
- 통과하면 CHANGELOG 반영 (버전 번호는 사용자가 정할 것)

## 7. 관련 메모리 (auto-memory, 이 세션 밖 영구 저장)

- `feedback_plugin_ecosystem_core_change_governance` — 플러그인 ~100개가 코어 계약에
  의존하므로, 플러그인 관련 코어 변경은 항상 먼저 물어볼 것 (theme_manifest 설계 시 특히 해당)
- `feedback_plugin_ecosystem_self_service_preference` — 커뮤니티 기능 요청은 직접 구현보다
  스펙 공유를 선호
- `feedback_public_repo_no_hardcoded_credentials` — 이 저장소는 공개 GitHub 저장소
  (leeyj/BookOasis)이므로 실제 키/URL을 기본값으로 하드코딩하지 말 것 (테마 작업과는 무관하지만
  같은 파일들 만지다 실수하지 않도록 재확인)
- `project_page_turn_experiment_pilot` — `experimental_page_turn.html`이 왜 격리돼 있는지 배경
