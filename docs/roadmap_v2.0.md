# 2.0 준비: 점진적 코드 컴포넌트화 로드맵

## Context

1.9.x 라인에서 기능적으로는 마무리 지점에 도달했고(스마트 추천 완료, 휴지통 락 이슈 수정 등), 더 이상 마이너 기능 패치보다는 2.0을 위한 구조 정리가 필요한 시점이다. 목표는 "코드 컴포넌트화" — 인라인 스타일과 거대 단일 파일, 반복되는 HTML 마크업, 그리고 mariadb/sqlite 리포지토리 중복을 정리해 유지보수 비용을 낮추는 것이다.

핵심 제약: **하루에 다 바꾸지 않는다.** 각 세션은 독립적으로 되돌릴 수 있는 작은 단위(파일 1~2개 또는 한 기능 영역) 하나만 처리하고, 그때그때 동작 확인 후 다음 단위로 넘어간다. 구글 드라이브 폴더링크 등록 기능은 이번 로드맵에서 제외(보류 상태 유지, 별도 논의 예정 — 상세 원인은 `docs/bug/` 참고용으로 추후 별도 문서화).

## 조사 결과 요약 (우선순위 근거)

- **인라인 스타일**: `static/js` + `templates` 전역에 `style="..."` 1,286회, 57개 파일에 분산. 기계적이고 리스크가 가장 낮음 → 1순위로 착수해 나머지 작업의 기반을 만든다.
- **프론트 JS 거대 파일**: `viewer_txt.js`(1011줄), `ui.js`(828줄), `book_context_menu.js`(690줄), `scheduler.js`(697줄), `audio_player.js`(710줄) 등이 여러 책임을 한 파일에 담고 있음.
- **HTML 템플릿**: `templates/components/`는 이미 `views/`, `settings/`, `modals/`로 어느 정도 분리돼 있음(24개 파일). 부족한 건 반복되는 마크업 조각(카드 배지, 탭 pill, 섹션 헤더+좌우 화살표 버튼 등)의 매크로/부분 템플릿화.
- **백엔드 리포지토리 중복**: `repositories/mariadb/*`와 `repositories/sqlite/*`가 파일당 거의 동일한 줄 수(예: `book_repository.py` 510 vs 526, `trash_repository.py` 125 vs 126)로 사실상 대부분 로직이 복붙 중복. 휴지통 락 버그를 두 파일에 각각 고쳐야 했던 게 이 구조의 직접적인 비용. 다만 이건 코어 데이터 접근 계층이라 리스크가 가장 크므로 마지막 트랙, 파일럿 1개로 시작.

## 진행 원칙

- 4개 트랙(A~D)은 서로 독립적 — 어떤 순서로도 진행 가능하지만, A(CSS)를 먼저 어느 정도 진행해두면 B/C 작업 시 옮길 인라인 스타일이 줄어 있어 더 수월함.
- 트랙 내에서는 파일/기능 단위로 티켓을 쪼개 순서대로 진행. 한 세션 = 티켓 1~2개.
- 매 티켓마다: 수정 → 정적 검증(`node --check`, `python -m py_compile`) → 가능하면 `/run` 스킬로 브라우저 확인 → 커밋 제안(사용자 승인 후).
- 순수 리팩터링이므로 동작/출력은 절대 바뀌면 안 됨 — 새 기능 추가 금지, 지금 없는 검증/에러 처리 추가 금지.

---

## 진행도

**트랙 순서 변경 (2026-08-12):** 원래 B→C 순서였으나, "B(거대 JS 분리)보다 C(반복 마크업 공용 헬퍼화)를 먼저 하는 게 안전하다"는 판단으로 **C를 B보다 먼저** 진행하기로 함. 이유: C에서 뽑아낼 공용 헬퍼가 어느 모듈에 들어갈지 B의 파일 분리 결과에 따라 달라지면 두 리팩터링이 서로 얽힘 → 작고 독립적인 새 파일로 먼저 헬퍼를 뽑아두고, 그 다음에 `ui.js` 등 거대 파일을 쪼개는 게 더 안전. 또한 `ui.js`도 결국 트랙 B에서 컴포넌트 단위로 분리 대상.

| 트랙 | # | 티켓 | 상태 | 완료일 |
| :--- | :-: | :--- | :--- | :--- |
| A | 1 | `tab_smart_recommend.js` 인라인 스타일 → CSS 클래스 | ✅ 완료 | 2026-08-12 |
| A | 2 | `ui.js`(`createBookCard` 등) 재사용 카드 스타일 클래스화 (부수적으로 `header_view.js`의 잠금배지 중복도 함께 제거) | ✅ 완료 | 2026-08-12 |
| A | 3 | `general_tab.html` 체크박스 row 패턴 정리 (`.settings-checkbox-row` 등 신설) | ✅ 완료 | 2026-08-12 |
| A | 4 | `dashboard.js` 자체 인라인 스타일(플러그인 위젯 카드, 통계 미니카드 등 별도 마크업, ~31곳) 정리 | ✅ 완료 | 2026-08-12 |
| C | 1 | 스크롤 행 섹션(헤더+화살표) 공용 헬퍼화 — `dashboard.js`/`tab_media_library.js`의 `scrollDashboardRow`/`initDashboardNavDelegation`과 `tab_smart_recommend.js`의 `initSmartRecNavDelegation` 통합 | ✅ 완료 | 2026-08-12 |
| C | 2 | 설정 탭 체크박스 row 매크로화 | ✅ 완료 | 2026-08-12 |
| B | 1 | `ui.js` → 스캔 활동 상태 폴링/팝오버를 `scan_activity_status.js`로 분리 | ✅ 완료 | 2026-08-12 |
| B | 2 | `scheduler.js` → 크론 헬퍼 UI를 `cron_helper.js`로 분리 | ✅ 완료 | 2026-08-12 |
| B | 3 | `audio_player.js` → `audio_player_modules/` 컨벤션 확장 (챕터 드로어를 `chapter_drawer.js`로 분리) | ✅ 완료 | 2026-08-12 |
| B | 7 | `book_context_menu.js`(690줄) — 응집도 높아 분리 지점 없음 | ⏭️ 스킵 | 2026-08-12 |
| B | 5 | `viewer/renderer.js`(825줄) — 성능 핫패스, 무리한 분리는 리스크만 키움 | ⏭️ 스킵 | 2026-08-12 |
| B | 4 | `audio_player_modules/mini_player_ui.js`(827줄) 클로저 분리 | ⏭️ 스킵 | 2026-08-12 |
| B | 6 | `viewer_txt.js`(1011줄) — TXT/EPUB이 공용 이벤트 핸들러 안에서 얽혀있어 리스크 질적으로 다름 | ⏸️ 보류 | - |
| D | 1 | `trash_repository.py` mariadb/sqlite 공용화 파일럿 | ⬜ 대기 | - |
| D | 2 | 파일럿 성공 시 소형 리포지토리 순차 확장 | ⬜ 대기 | - |

상태 값: ⬜ 대기 / 🔄 진행중 / ✅ 완료 / ⏸️ 보류 / ⏭️ 스킵(의도적으로 하지 않기로 결정)

---

## 트랙 A — 인라인 스타일 → CSS 클래스 (최우선, 저위험)

**패턴**: JS 문자열 템플릿 안 `style="display:flex; ...` 반복 블록을 `static/css/style.css`에 이름 있는 클래스로 옮기고, 마크업에는 클래스명만 남긴다. 이미 있는 관례(`.dashboard-row-container`, `.btn-nav-arrow`, `.book-card`)를 그대로 확장하는 방식 — 새 디자인 시스템을 만들지 않는다.

첫 티켓 후보 (반복 빈도/최근 작업 인접성 기준):
1. `static/js/tab_smart_recommend.js` — 최근에 만든 파일이라 인라인 스타일 밀도가 가장 높고 범위가 작아 시범 케이스로 적합
2. `static/js/dashboard.js` + 관련 카드 렌더 함수 (`ui.js`의 `createBookCard`) — 가장 많이 재사용되는 카드 스타일
3. `templates/components/settings/general_tab.html`의 체크박스 row 패턴(`library-form-group-row` 인라인 style 반복) — 이미 클래스명은 있는데 인라인 style이 같이 붙어있는 애매한 상태부터 정리

## 트랙 C — HTML 템플릿 반복 부품화 (중위험, B보다 먼저 진행)

**패턴**: JS로 문자열 조립 중인 반복 마크업(섹션 헤더+좌우 화살표 버튼, 탭 pill, 카드 배지 등)을 Jinja 매크로나 JS 헬퍼 함수로 부품화. `library_dashboard.html`의 섹션 헤더(`.btn-nav-arrow` 페어)가 `tab_smart_recommend.js`에도 그대로 복붙돼 있는 게 좋은 예 — 이런 걸 공용 헬퍼(예: `buildScrollableRowSection()`)로 뽑아내면 다음에 또 복붙 안 해도 됨.

첫 티켓 후보:
1. 스크롤 가능한 행 섹션(헤더+화살표+`.dashboard-row-container`) 공용 JS 헬퍼화 — `dashboard.js`/`tab_media_library.js`의 `scrollDashboardRow`/`initDashboardNavDelegation`과 `tab_smart_recommend.js`의 `initSmartRecNavDelegation`을 하나로 통합
2. 설정 탭 체크박스 row(`library-form-group-row`) 매크로화 — `general_tab.html`에 반복 다수

## 트랙 B — 프론트 JS 거대 파일 분리 (중위험, C 이후 진행)

**패턴**: 파일 내 기능 단위 경계를 찾아 별도 모듈로 추출하고 원본에서 import. 전역 `window.*` 바인딩은 유지(다른 곳에서 참조 중이므로 깨면 안 됨).

**2026-08-12 추가 조사**: `static/js` 전체(하위 디렉토리 포함) 재조사 결과, 원래 목록(ui.js/viewer_txt.js/book_context_menu.js/scheduler.js) 4개 외에 대형 파일이 더 있었고, 일부는 함수 단위로 뜯어보니 이미 분리 대상이 명확히 드러남. 아래 순서로 갱신:

1. **`static/js/ui.js`(828줄)** — `createBookCard`/그리드 렌더링(30~570줄)과 **스캔 활동 상태 폴링/팝오버**(573~828줄: `renderScanActivity`, `initScanActivityPopover`, `updateCategoryScanSpinners`, `startSystemStatusPolling` 등)가 완전히 무관한 두 기능. 후자를 `scan_activity_status.js`로 추출하면 파일이 절반 가까이 줄어듦 — 가장 안전하고 명확한 첫 스텝
2. **`static/js/scheduler.js`(697줄)** — 스케줄 목록/상태 렌더링과 **크론 표현식 헬퍼 UI**(392~547줄: `buildCronFromHelper`, `parseHelperStateFromCron`, `refreshCronHelperVisibility` 등)가 사실상 독립적. `cron_helper.js`로 분리 가능
3. **`static/js/audio_player.js`(710줄, 36개 함수)** — 이미 `audio_player_modules/`(progress_sync.js, lifecycle_shortcuts.js 등) 서브모듈 컨벤션이 존재하니 그 패턴을 확장해서 계속 나누면 됨
4. **`static/js/audio_player_modules/mini_player_ui.js`(827줄)** — (신규 발견) "미니 플레이어 UI/드래그/뷰 모드 전담"이라는 단일 책임이지만 `createMiniPlayerUiController(deps)` 클로저 하나가 827줄 — 함수 추출이 아니라 **큰 클로저 하나를 여러 개로 쪼개는** 다른 성격의 작업이라 우선순위 낮게
5. **`static/js/viewer/renderer.js`(825줄, 23개 함수)** — (신규 발견) 이미 `viewer/` 하위로 컴포넌트화된 뷰어 모듈 중 하나. 여기서 더 쪼갤지는 실제로 들여다봐야 판단 가능
6. **`static/js/viewer_txt.js`(1011줄) — 보류 (트랙 B 대상에서 제외, 아래 사유 참고).**
   ⚠️ **정정**: "아직 안 쪼갠 거대 파일"이 아니다. EPUB 쪽 순수 로직(챕터 콘텐츠 요청/프리로드/TOC)은 이미 `viewer/epub_loader.js`, `viewer/txt_toc.js` 등으로 분리돼 있고, `viewer_txt.js`에는 이를 로컬 클로저 상태(`currentChunkIdx`, `txtChunks`)에 연결하는 얇은 래퍼 6개만 남아있음(103~125줄).
   진짜 문제는 파일 절반을 차지하는 **`initTxtViewer` 함수 하나(127~530줄, ~400줄)**. 앞부분(~70줄, `if (isEpub) {...}`)은 EPUB 전용 초기화라 깔끔하게 분리 가능하지만, 그 뒤 스크롤/리사이즈/진행률 저장 리스너들은 **TXT/EPUB이 하나의 공용 이벤트 핸들러 안에서 `isEpubMode` 인라인 분기로 같이 처리**되고 있음(예: 진행률 저장 payload를 `isEpubMode ? {epub_session:...} : ...` 식으로 분기). 즉 복붙된 두 로직이 아니라 "한 리스너가 포맷 두 개를 겸함" 구조라, 물리적으로 나누려면 리스너 자체를 복제하거나 재설계해야 해서 리스크가 확 올라감.
   → 지금은 순수 사이즈만으로 손댈 이유가 부족(실제 유지보수 불편을 겪은 적 없음) + 리스크가 다른 항목들과 질적으로 다름 → **트랙 B에서 제외, 보류.** 나중에 이 파일을 진짜 건드릴 일이 생기면(버그 수정 등) 그 김에 `if (isEpub) {...}` 초기화 블록(127+30~127+100줄 부근)만 국소적으로 떼는 것부터 시작할 것 — 공용 리스너 재설계는 시도하지 말 것.
7. `static/js/book_context_menu.js`(690줄) — 함수 목록을 봤을 때 전부 컨텍스트 메뉴 관련(포지셔닝/플러그인 아이템/닫기/액션)이라 응집도가 높음. 분리 이득이 상대적으로 적어 보여 우선순위 낮음

## 트랙 D — 백엔드 mariadb/sqlite 리포지토리 중복 정리 (최고위험, 파일럿 1개부터)

**패턴**: 전체 통합/재작성은 하지 않는다(코어 데이터 계층 전체를 건드리는 건 리스크가 과함). 대신 이미 완전히 이해하고 있는 파일 하나를 파일럿으로 삼아 "SQL은 한 곳에, 방언 차이(`%s` vs `?`, `dict(row)` 등)만 어댑터로 분리" 패턴이 실제로 유지보수 비용을 줄이는지 검증 후 확장 여부를 다시 논의한다.

첫 티켓:
1. `repositories/mariadb/trash_repository.py` + `repositories/sqlite/trash_repository.py` 파일럿 — 두 파일을 동시에 고친 경험이 있어 두 구현의 차이를 가장 잘 파악하고 있는 상태. 공용 SQL 정의 + 방언 어댑터 패턴을 여기서만 시도해보고, 실제로 코드량/버그 리스크가 줄었는지 확인 후 다른 리포지토리로 확장할지 결정
2. (파일럿 성공 시) `book_offset_repository.py`, `settings_repository.py` 등 작고 단순한 파일부터 순차 확장

---

## 검증 방법

- JS 변경: `node --check <file>` 로 문법 확인
- Python 변경: `python -m py_compile <file>`
- 가능하면 `/run` 스킬로 실제 서버 띄워서 스타일/동작 회귀 없는지 스크린샷 확인 (특히 트랙 A/C는 시각적 회귀가 핵심 리스크)
- 트랙 D는 회귀 방지가 특히 중요 — 기존 테스트(`tests/test_repair_mariadb_admin.py` 등 유사 패턴) 참고해 파일럿 대상에 대한 최소 스모크 테스트 작성 고려

## 다음 세션 시작점

**트랙 A 완료 (2026-08-12).** 인라인 스타일 → CSS 클래스 이전을 `tab_smart_recommend.js`, `ui.js`(+ 부수적으로 `header_view.js`), `general_tab.html`, `dashboard.js` 전반에 걸쳐 마쳤다. 각 티켓은 `node --check` / CSS 브레이스 균형 검증을 통과했고, 사용자가 스마트 추천 화면을 직접 확인해 정상 동작을 확인했다(A-4는 코드 작업만 완료, 별도 시각 확인은 다음 세션에서 진행).

**트랙 순서 C→B로 변경 (2026-08-12).**

C-1 완료: `static/js/scrollable_row_nav.js` 신설(`scrollRow`, `buildRowNavButtonsHtml`, `initScrollableRowNavDelegation`). `dashboard.js`의 `scrollDashboardRow`/`tab_media_library.js`의 `initDashboardNavDelegation`과 `tab_smart_recommend.js`의 `initSmartRecNavDelegation`을 모두 제거하고 이 모듈로 통합. 버튼 속성도 `data-role="dashboard-row-nav" data-row="history"`(타입→id 매핑) 방식에서 `data-scroll-row-nav="<rowId>"`(id 직접 지정) 방식으로 통일해 `library_dashboard.html`과 `tab_smart_recommend.js` 양쪽이 동일 규약을 쓰도록 정리. CSS도 `.section-nav-btns`/`.section-nav-btns--hidden` 공용 클래스 신설, 기존 `.smart-rec-section-nav`(거의 동일한 중복 규칙) 제거.

C-2 완료: `templates/components/settings/general_tab.html` 최상단에 `{% macro checkbox_row(id, name, checked, i18n_key, extra_class, input_class) %}` 정의(이 파일 전용, 이 프로젝트 최초의 Jinja 매크로 사용 사례). 반복되던 체크박스 row 10개를 전부 `{% call checkbox_row(...) %}라벨{% endcall %}` 한 줄 호출로 교체. Jinja `Environment.get_template().render()`로 실제 렌더링해 결과 HTML이 매크로 적용 전과 구조적으로 100% 동일함을 확인(각 row의 id/name/checked/data-i18n/hint span까지 정확히 일치).

**트랙 C 완료 (2026-08-12).**

**트랙 B 추가 조사 완료 (2026-08-12, 실행 전).** `static/js` 전체를 다시 스윕하고 각 대형 파일의 함수 구조를 확인해 트랙 B 티켓을 7개로 재정의했다(위 "트랙 B" 섹션 참고). 아직 실제 분리 작업은 착수 전이다.

**트랙 B 1~3번 완료 (2026-08-12).**

- B-1: `static/js/scan_activity_status.js` 신설. `ui.js`의 573~828줄(스캔 활동 폴링/팝오버/카테고리 스피너: `renderScanActivity`, `initScanActivityPopover`, `updateCategoryScanSpinners`, `startSystemStatusPolling` 등)을 통째로 이동. `ui.js`에는 `import './scan_activity_status.js';`만 남겨 모듈 그래프상 사이드이펙트(폴링 시작, DOMContentLoaded 초기화)가 기존과 동일한 시점에 정확히 1회 실행되도록 보존. `ui.js` 828→561줄.
  - **[해결됨, 2026-08-12]** 이관 과정에서 발견했던 `window.addEventListener('resize', ...)`의 정의되지 않은 전역 함수 `syncSystemTickerLayout()` 참조 버그: 조사 결과 `#system-ticker-footer` 요소 자체가 현재 어떤 템플릿/JS에서도 생성되지 않는 완전히 죽은 기능(예전에 있던 "시스템 속보 푸터" 기능이 마크업만 걷어내고 CSS·이 리스너는 안 치운 채 남은 잔재)이라, `footer`가 항상 `null`이라 실제로는 절대 호출되지 않는 도달 불가능한 코드였음. 기능을 되살리는 대신 `scan_activity_status.js`의 해당 `resize` 리스너를 삭제. 사용자 확인 후 같은 기능의 고아 CSS도 전부 함께 제거: `static/css/style.css`의 `.system-ticker-footer`/`.ticker-title`/`.ticker-wrap`/`.ticker-content`/`@keyframes tickerSlideUp`/`@keyframes marquee`(~70줄)와 `body.has-system-ticker` 관련 규칙 2건(1037~1043줄), `static/css/mobile.css`의 `body.has-system-ticker` 규칙 3건 + `.system-ticker-footer` 반응형 규칙(~20줄). `grep`으로 전체 저장소에 `system-ticker`/`has-system-ticker` 잔여 참조 없음을 확인, CSS 중괄호 균형도 재검증.
- B-2: `static/js/cron_helper.js` 신설. `scheduler.js`의 크론 헬퍼 서브시스템(`pad2`, `buildCronFromHelper`, `parseHelperStateFromCron`, `hydrateCronHelperFromCron`, `onCronHelperModeChange`, `updateCronHelperSummary`, `applyCronHelperToInput`)을 이동. `scheduler.js`의 `openScanSettingsModal` 내부 `cronInput.oninput` 핸들러가 비공개 함수 `refreshCronHelperSummary()`를 직접 호출하던 부분은 동일 동작의 공개 wrapper `updateCronHelperSummary()`(import)로 교체. `scheduler.js` 698→522줄.
- B-3: 기존 `audio_player_modules/` 컨벤션(`createXxx(deps)` 팩토리 + getter/콜백 주입)을 그대로 따라 `audio_player_modules/chapter_drawer.js` 신설, `renderChapterList`/`toggleAudioChapterDrawer`/`selectChapterTrack`(챕터 드로어 렌더링·토글·트랙 선택)을 분리. 이 세 함수는 `currentAudiobookData`/`currentTrackIndex` 등 핵심 재생 상태를 읽기만 하고 쓰지 않아, `audio_player.js`의 다른 함수들(볼륨/배속/취침타이머 등)보다 훨씬 안전하게 분리 가능했음 — 나머지는 `audioInstance.playbackRate` 등 핵심 재생 상태를 직접 변경하므로 후순위로 미룸(아래 참고). `audio_player.js` 710→695줄.

세 티켓 모두 `node --check`로 문법 검증 완료. 브라우저 실동작 확인은 아직 안 함 — 다음 세션 시작 시 `/run`으로 최근 읽음 그리드, 오디오북 재생 화면, 설정 스케줄 탭을 열어 회귀 없는지 확인할 것.

**남은 트랙 B 우선순위 재분석 (2026-08-12, "리스크 낮은 것부터" 기준으로 재정렬):**

| 순위 | 티켓 | 근거 |
| :-: | :--- | :--- |
| 1 | B-7 `book_context_menu.js` | 재확인 결과 포지셔닝/플러그인 아이템/닫기/롱프레스가 전부 "컨텍스트 메뉴"라는 하나의 응집된 책임 — 쪼갤 지점이 없음. 실질적으로 "조사 후 분리 불필요로 종결"하는 낮은 리스크·낮은 노력 티켓. 다음 세션 시작점으로 가장 적합(빠르게 닫고 다음으로 넘어갈 수 있음). |
| 2 | B-5 `viewer/renderer.js`(825줄) | Web Worker(이미지 디코딩)/Blob URL 캐시/스크롤 옵저버가 모듈 최상위 `let`/`Map`/`Set` 상태로 얽혀 있음 — 코믹/웹툰 렌더링 핫패스라 성능 회귀 리스크가 있지만, 아직 "실제로 쪼갤 지점이 있는지" 조사 자체를 안 한 상태라 판단 보류. B-4보다는 먼저 조사할 가치가 있음(조사 결과 "쪼갤 필요 없음"으로 끝날 수도 있음 — B-7과 비슷하게 종결될 가능성 있음). |
| 3 | B-4 `audio_player_modules/mini_player_ui.js`(827줄) | `createMiniPlayerUiController(deps)` 팩토리 **하나**가 827줄 — 이번 세션에서 했던 B-1/B-2/B-3처럼 "이미 분리된 독립 기능을 기계적으로 이동"하는 게 아니라, **드래그 상태(`miniBarDragState`)/축소 상태(`miniBarCollapsed`)/트랙 리스트 렌더 상태를 공유하는 하나의 큰 클로저를 여러 개로 새로 쪼개는" 설계 작업**이라 이 프로젝트에서 아직 시도해본 적 없는 패턴. 드래그·뷰모드 전환은 수동 상호작용 테스트 없이는 회귀를 잡기 어려워 리스크가 가장 높음 → 최후순위 유지. |
| - | B-6 `viewer_txt.js`(1011줄) | 기존 결정 유지: 트랙 B 범위에서 완전히 제외, 보류. |

**B-4~B-7 전부 스킵 결정 (2026-08-12, 사용자 판단).** 사용자가 "유지보수에 크게 어려움이 있지 않고, 무리하게 쪼갰다가는 위험도만 커진다"는 이유로 B-4/B-5/B-7을 조사조차 하지 않고 명시적으로 스킵하기로 결정 — 위 우선순위 분석은 "이 순서로 진행"이 아니라 "만약 다시 손댈 일이 생기면 이 순서로"의 참고 자료로만 남긴다. B-6(`viewer_txt.js`)은 기존 사유(TXT/EPUB이 공용 이벤트 핸들러에서 얽혀 있어 리스크 질적으로 다름)로 이미 보류 상태였으므로 동일하게 유지. **트랙 B는 이것으로 종료** — 사이즈만으로 손댈 이유가 부족한 파일을 억지로 쪼개지 않는다는 이 프로젝트의 "필요 이상으로 추상화하지 않는다" 원칙과 일치하는 결정.

**트랙 B 종료 (2026-08-12).** A/B/C 모두 완료. **남은 건 트랙 D(백엔드 mariadb/sqlite 리포지토리 중복 정리)뿐** — 다음 세션은 D-1(`trash_repository.py` 파일럿)부터 시작한다. 착수 전 반드시 다시 한번 "SQL은 한 곳에, 방언 차이만 어댑터로 분리" 패턴이 정말 필요한지, 파일럿 범위를 벗어나지 않는지 확인할 것(트랙 D 섹션 참고 — 전체 재작성 금지, 파일럿 1개로 제한). 또한 B-1~3에서 브라우저 실동작 확인(`/run`)이 아직 안 됐다는 점도 함께 확인하고 넘어갈 것.
