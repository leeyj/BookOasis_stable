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
| D | 1 | `trash_repository.py` mariadb/sqlite 공용화 파일럿 | ✅ 완료 | 2026-08-13 |
| D | 2 | 파일럿 성공 시 소형 리포지토리 순차 확장 | ⏭️ 스킵 | 2026-08-13 |

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

**D-1 완료 (2026-08-13).** 착수 전 재검토에서 "정말 필요한가"부터 다시 물었고, 두 가지로 결론:

- **필요성**: B-4~7과 달리 추측성 리스크가 아니라 실제 이력이 있음. git log(`8910e21`)에서 확인한 "휴지통 락 이슈" 수정이 중첩 서브쿼리 DELETE → 확정 후 삭제 패턴으로의 **로직 변경**이었고, 이걸 mariadb/sqlite 두 파일에 동일하게 반영해야 했던 실제 이중 유지보수 비용이 있었음.
- **MSSQL 확장성 고려**: 쿼리 중앙화 작업의 최종 목표인 3번째 백엔드(MSSQL) 지원을 반영해 설계를 조정. pyodbc(MSSQL 표준 드라이버)의 기본 paramstyle이 `qmark`(`?`)라 sqlite와 동일 — 어댑터를 mariadb/sqlite 이분법이 아니라 `placeholder: str` 하나만 받는 순수 함수로 짰기 때문에, 나중에 MSSQL을 추가할 때 `repositories/mssql/trash_repository.py`에 `placeholder='?'`로 공용 함수를 호출하는 얇은 래퍼만 추가하면 됨(공용 SQL 로직은 무수정). row의 dict 접근(`row['id']`, `dict(row)`)은 repository 레이어가 아니라 `database.py` 커넥션 레이어 책임(mariadb는 이미 `MariadbCursorWrapper`로 처리 중) — MSSQL 추가 시 그쪽에 `MssqlCursorWrapper`를 붙이면 되고, 이 파일 설계에는 영향 없음. 이 파일의 SQL은 `LIMIT`/`TOP`/`AUTO_INCREMENT` 등 방언 전용 문법을 쓰지 않아 플레이스홀더 문자 하나만 파라미터화하는 것으로 충분했음.

**구현**: `repositories/trash_repository_shared.py` 신설(126줄, SQL 로직 전체 + `placeholder` 인자로 방언 흡수). `repositories/mariadb/trash_repository.py`·`repositories/sqlite/trash_repository.py`는 각각 `_PLACEHOLDER = '%s'`/`'?'`로 공용 함수를 호출하는 얇은 래퍼로 축소(126/127줄 → 각 47줄). `TrashRepository` 클래스명·메서드 시그니처는 그대로 유지해 호출부(`services/trash_service.py`) 무수정.

**부수 발견(수정함)**: 공용화 과정에서 sqlite 쪽에만 `restore_books`/`fetch_book_covers`/`hard_delete_books_transaction`의 "빈 리스트면 조기 반환" 가드가 빠져 있던 걸 발견 — mariadb에는 있었음. 특히 `fetch_book_covers`/`hard_delete_books_transaction`은 빈 리스트가 들어오면 `IN ()` 구문 오류로 죽을 수 있는 잠재 버그였음(현재 호출부가 빈 리스트로 호출한 적이 없어 아직 발현 안 됨). 공용화하면서 mariadb의 안전한 쪽으로 통일 — "한 파일만 고쳐지고 다른 파일은 안 고쳐지는" 패턴이 트랙 D를 시작하기도 전에 이미 한 번 더 실증된 사례.

**검증**: `python -m py_compile` 통과. `DB_ENGINE=sqlite`/`mariadb` 양쪽 모두 `import repositories`로 실제 로드해 `TrashRepository`가 정상 해석되고 순환참조 없음을 확인(기존 `repositories/series_search_query.py` 공용 모듈 패턴과 동일한 임포트 구조). **실서버 동작도 사용자가 직접 확인(2026-08-13)** — 휴지통에서 29권 영구 삭제 실행, 로그상 `hard_delete_books_transaction` 경로(확정 id 조회 → 종속 테이블 정리 → books 삭제 → 미참조 커버 GROUP BY 판별 → 커버 파일 물리 삭제)가 정상 동작해 29개 미참조 커버가 정확히 삭제되고 "Successfully hard deleted 29 books from DB and storage" 로그로 마무리됨. 복구(`restore_books`) 경로는 아직 실동작 확인 전.

**D-2 스킵 결정 (2026-08-13, 보수적 재검토 후).** 로드맵이 다음 후보로 지목했던 `book_offset_repository.py`/`plugin_repository.py`/`settings_repository.py` 등을 실제로 diff해본 결과, 트래시 파일럿과 성격이 달랐다:

- 플레이스홀더(`%s`/`?`)만 정규화하고 남는 diff가 트래시(8줄)보다 훨씬 큼(예: `settings_repository.py` 110줄, `metadata_repository.py` 242줄 — 심지어 두 파일 다 줄 수는 mariadb/sqlite 동일한데도).
- `settings_repository.py`/`plugin_repository.py`는 UPSERT 문법 자체가 `REPLACE INTO`(mariadb) vs `INSERT OR REPLACE`(sqlite)로 진짜 갈림 — `placeholder: str` 하나로 흡수 안 되고, MSSQL(`MERGE`/`IF EXISTS`)까지 고려하면 3-way 분기가 필요해 트래시가 증명한 "얇은 래퍼" 이득이 사라짐.
- git log 확인 결과 트래시처럼 "동일 버그를 양쪽에 동일하게 고친" 이중 유지보수 이력이 다른 파일들엔 없었음 — 오히려 `book_offset`/`book_scan`/`scheduler`/`settings_repository.py`는 sqlite 쪽 커밋 수가 mariadb보다 많아(반영 누락 가능성 신호), 트랙 D가 다루는 "중복이라 위험" 문제와는 다른 별개 이슈로 확인됨(이번 세션 범위 밖).

B-4~7 스킵 때 세운 원칙("실제 유지보수 불편을 겪은 적 없으면 무리해서 안 쪼갠다")을 그대로 적용해 **D-2는 스킵, 트랙 D는 D-1 파일럿 1개로 완전히 종료.**

**부수 작업 (D-2 조사 중 발견, 트랙 D와 무관하게 별도 처리): `LRUCache` 3중복 정리.** `book_offset_repository.py` 조사 과정에서 애초 "sqlite에만 있는 LRU 캐시(레디스 이전 잔재?)"라는 가설이 나왔으나 확인 결과 **틀림** — `_LRUCache` 클래스는 mariadb/sqlite 양쪽에 동일하게 존재했고(제가 diff를 잘못 읽어 처음에 "sqlite에만 있다"고 잘못 보고했음), git 이력상 Redis가 있던 적도 없는 파일. 실제 원인은 `api/cache.py`에 이미 있는 거의 동일한 `LRUCache`를 못 쓰고 복붙한 것 — `repositories/*`에서 `from api.cache import LRUCache`를 하면 `api/__init__.py`가 먼저 실행되며 블루프린트 체인이 `repositories`를 다시 임포트해 순환참조가 걸리기 때문(주석에 명시돼 있었음). Redis(`utils/redis_helper.py`)는 읽기 진행률 쓰기 버퍼링용으로 이 오프셋 캐시와는 무관.

해결: 의존성 없는 leaf 모듈 `utils/lru_cache.py` 신설(`LRUCache` 클래스, threading/collections만 사용). `api/cache.py`는 자체 정의를 지우고 여기서 import(`SizedLRUCache`는 로직이 달라 그대로 유지). `repositories/mariadb/book_offset_repository.py`·`repositories/sqlite/book_offset_repository.py`도 인라인 `_LRUCache` 정의를 지우고 동일하게 import. `class _LRUCache`/`class LRUCache` 정의가 3곳 → 1곳으로. 검증: `python -m py_compile` 통과, `DB_ENGINE=sqlite`/`mariadb` 양쪽 + `api.cache`를 먼저 임포트하는 순서/나중에 임포트하는 순서 모두 순환참조 없이 정상 로드 확인, `api.cache.LRUCache is utils.lru_cache.LRUCache`로 동일 클래스 공유까지 확인.

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

세 티켓 모두 `node --check`로 문법 검증 완료. **브라우저 실동작 확인도 사용자가 직접 완료(2026-08-13)** — 최근 읽음 그리드/스캔 활동 팝오버, 오디오북 재생 화면(챕터 드로어 포함), 설정 스케줄 탭(크론 헬퍼 포함) 모두 회귀 없음 확인.

**남은 트랙 B 우선순위 재분석 (2026-08-12, "리스크 낮은 것부터" 기준으로 재정렬):**

| 순위 | 티켓 | 근거 |
| :-: | :--- | :--- |
| 1 | B-7 `book_context_menu.js` | 재확인 결과 포지셔닝/플러그인 아이템/닫기/롱프레스가 전부 "컨텍스트 메뉴"라는 하나의 응집된 책임 — 쪼갤 지점이 없음. 실질적으로 "조사 후 분리 불필요로 종결"하는 낮은 리스크·낮은 노력 티켓. 다음 세션 시작점으로 가장 적합(빠르게 닫고 다음으로 넘어갈 수 있음). |
| 2 | B-5 `viewer/renderer.js`(825줄) | Web Worker(이미지 디코딩)/Blob URL 캐시/스크롤 옵저버가 모듈 최상위 `let`/`Map`/`Set` 상태로 얽혀 있음 — 코믹/웹툰 렌더링 핫패스라 성능 회귀 리스크가 있지만, 아직 "실제로 쪼갤 지점이 있는지" 조사 자체를 안 한 상태라 판단 보류. B-4보다는 먼저 조사할 가치가 있음(조사 결과 "쪼갤 필요 없음"으로 끝날 수도 있음 — B-7과 비슷하게 종결될 가능성 있음). |
| 3 | B-4 `audio_player_modules/mini_player_ui.js`(827줄) | `createMiniPlayerUiController(deps)` 팩토리 **하나**가 827줄 — 이번 세션에서 했던 B-1/B-2/B-3처럼 "이미 분리된 독립 기능을 기계적으로 이동"하는 게 아니라, **드래그 상태(`miniBarDragState`)/축소 상태(`miniBarCollapsed`)/트랙 리스트 렌더 상태를 공유하는 하나의 큰 클로저를 여러 개로 새로 쪼개는" 설계 작업**이라 이 프로젝트에서 아직 시도해본 적 없는 패턴. 드래그·뷰모드 전환은 수동 상호작용 테스트 없이는 회귀를 잡기 어려워 리스크가 가장 높음 → 최후순위 유지. |
| - | B-6 `viewer_txt.js`(1011줄) | 기존 결정 유지: 트랙 B 범위에서 완전히 제외, 보류. |

**B-4~B-7 전부 스킵 결정 (2026-08-12, 사용자 판단).** 사용자가 "유지보수에 크게 어려움이 있지 않고, 무리하게 쪼갰다가는 위험도만 커진다"는 이유로 B-4/B-5/B-7을 조사조차 하지 않고 명시적으로 스킵하기로 결정 — 위 우선순위 분석은 "이 순서로 진행"이 아니라 "만약 다시 손댈 일이 생기면 이 순서로"의 참고 자료로만 남긴다. B-6(`viewer_txt.js`)은 기존 사유(TXT/EPUB이 공용 이벤트 핸들러에서 얽혀 있어 리스크 질적으로 다름)로 이미 보류 상태였으므로 동일하게 유지. **트랙 B는 이것으로 종료** — 사이즈만으로 손댈 이유가 부족한 파일을 억지로 쪼개지 않는다는 이 프로젝트의 "필요 이상으로 추상화하지 않는다" 원칙과 일치하는 결정.

**트랙 B 종료 (2026-08-12).** A/B/C 모두 완료. **남은 건 트랙 D(백엔드 mariadb/sqlite 리포지토리 중복 정리)뿐** — 다음 세션은 D-1(`trash_repository.py` 파일럿)부터 시작한다. 착수 전 반드시 다시 한번 "SQL은 한 곳에, 방언 차이만 어댑터로 분리" 패턴이 정말 필요한지, 파일럿 범위를 벗어나지 않는지 확인할 것(트랙 D 섹션 참고 — 전체 재작성 금지, 파일럿 1개로 제한). 또한 B-1~3에서 브라우저 실동작 확인(`/run`)이 아직 안 됐다는 점도 함께 확인하고 넘어갈 것.

**D-1 완료, 트랙 D 파일럿 종료 (2026-08-13).** 상세 내역은 위 "트랙 D" 섹션 참고. 요약: 필요성 재검토(실제 이중 유지보수 이력 확인) → MSSQL 3번째 백엔드 목표를 반영한 `placeholder` 파라미터화 설계로 `repositories/trash_repository_shared.py` 신설 → mariadb/sqlite 두 파일을 얇은 래퍼로 축소 → 부수적으로 sqlite 쪽 누락 가드 3건 발견·수정 → 컴파일/임포트 검증 완료. **A/B/C/D 트랙 전부 종료 (2026-08-13).** D-2는 스킵 결정으로 로드맵상 계획된 작업은 모두 마무리됐다. 남은 것: ① D-1의 `restore_books`(도서 복구) 경로는 아직 실동작 확인 전(영구 삭제 경로만 확인됨) — 기회가 되면 확인. ② `LRUCache` 중복 정리(부수 작업)는 컴파일/임포트 검증까지 완료했으나 브라우저 실동작 확인(뷰어에서 ZIP 코믹/웹툰 열람 시 오프셋 캐시 정상 동작)은 아직 안 함. ③ 이 로드맵 자체가 사실상 완료 상태이므로, 다음에 새 작업을 시작한다면 이 문서 갱신보다 새 이슈/로드맵 문서를 여는 게 맞을 수 있음.

---

## 트랙 E — 2026-08-17 대규모 패치 세션 이후 컴포넌트화 (새 이슈, 이 로드맵 종료 후 별도 착수)

기존 A/B/C/D 로드맵은 2026-08-13에 완전히 종료됐으나, 2026-08-17에 MariaDB GRANT/영상 강좌/플러그인/모바일 오디오 등 대규모 버그픽스 세션을 진행한 뒤 "코드 정리가 필요할 것 같다"는 요청으로 신규 서베이를 수행. 우선순위 1로 지목된 `database.py::init_databases()`부터 착수.

**E-1 완료 (2026-08-17): `database.py::init_databases()` 665줄 단일 함수 분할.**
- 이번 세션에만 124줄 늘어 총 1446줄이 된 `database.py`에서, `init_databases()` 하나가 665줄(781~1439행)을 차지 — 스키마 생성/인덱스/중복정리/설정시딩/관리자계정/즐겨찾기마이그레이션/권한시딩/오디오북백필/시리즈요약까지 서로 무관한 10개 단계가 한 함수에 나열돼 있었음. 이번 세션의 GRANT 크래시 버그·진단로그 개선도 전부 이 함수 안에서 발생.
- **구현**: 순수 리팩터링(로직 변경 없음). `schema`/`indexes_schema` 지역 변수(합쳐서 ~394줄의 순수 SQL 텍스트)를 모듈 레벨 상수 `_SCHEMA_SQL`/`_INDEXES_SQL`로 승격. for-loop 본문을 7개의 이름 있는 헬퍼 함수로 분리: `_connect_and_init_schema`, `_migrate_schema_and_dedupe_progress`, `_create_indexes_and_cleanup_fts`, `_seed_settings_and_admin`, `_seed_category_permissions`, `_backfill_audiobook_last_listened_at`, `_rebuild_series_summary_if_needed`. `init_databases()` 자체는 이제 각 헬퍼를 순서대로 호출하는 ~20줄짜리 오케스트레이터.
- **검증 방법**: (1) `python -m py_compile`. (2) 원본과 리팩터링본을 공백/주석 제외 정규화해 `difflib`로 비교 — 함수 경계 재배치 외에 SQL/로직 텍스트가 단 한 줄도 유실/변경되지 않았음을 확인. (3) `DB_ENGINE=sqlite`/`mariadb` 양쪽 모두 `import database` + `import repositories` 순환참조 없이 로드됨을 확인(트랙 D 파일럿과 동일한 검증 스타일). (4) **실제 `init_databases()` 실행 검증 중 리팩터링 자체의 버그를 하나 발견**: `_connect_and_init_schema`의 성공 경로에 `return conn, cursor`가 누락돼 있어(원본 코드는 for-loop 안에 인라인이라 반환문이 필요 없었으나, 함수로 뽑아내며 빠뜨림) `TypeError: cannot unpack non-iterable NoneType`가 실제로 재현됨 — 즉시 수정 후 재검증, 정상 동작 확인.
- **부작용(의도치 않음, 데이터 손상 없음)**: 위 (4) 검증 과정에서 격리된 임시 디렉터리를 쓰려 했으나, `DB_GENERAL_PATH` 등 경로 상수가 모듈 **import 시점**에 `BASE_DIR` 기준으로 고정되는 구조라 런타임에 `database.BASE_DIR`을 바꿔도 반영되지 않음 — 결과적으로 로컬 Windows 체크아웃의 **실제 `db/` 폴더**(예: `media_general.db` 1.7GB)에 대고 두 번(리팩터링본 1회, 원본 1회 비교차) 실행됨. `init_databases()`는 애초에 매 서버 부팅마다 실행되는 멱등 함수(`IF NOT EXISTS`, 없을 때만 시딩)라 데이터 손상은 없었으나, 사용자에게 투명하게 보고함. 격리 테스트가 다시 필요하면 `DB_DIR`/경로 상수를 함수 인자로 주입 가능하게 바꾸거나, `importlib.reload` 전에 환경변수를 먼저 세팅해야 함 — 이번엔 그렇게 하지 않아 발생한 문제.

**남은 후보 (착수 전, 우선순위 순)**:
- E-2: `tools/lazy_scanner.py::run_lazy_cover_extraction()` (485줄 단일 함수) — 이번 다일간 작업 기간 반복 버그(데드코드 순서, 로깅 순서, 배치 크기)가 전부 이 함수 안에서 발생. 단계별 분리 시 최소 순서 관련 버그는 예방 가능했을 것으로 추정.
- (참고, 재제안 금지) `mini_player_ui.js`(827줄)는 기존 B-4로 이미 조사·명시적 스킵됨. `reading_progress_repository.py` mariadb/sqlite 중복은 `CONCAT`/`INSERT IGNORE`/`FORCE INDEX` 등 실제 방언 차이가 커 D-2와 동일한 사유로 스킵 대상.

**E-2 완료 (2026-08-17, 부분 분리로 범위 축소): `tools/lazy_scanner.py::run_lazy_cover_extraction()`.**

착수 전 구조를 다시 확인한 결과, `init_databases()`(E-1)와 성격이 크게 다르다는 걸 발견했다:
- E-1의 10단계는 db_type별로 서로 독립적인 순차 단계였던 반면, 이 함수는 `db_type 루프 → 폴더 그룹 루프 → 개별 도서 루프` 3중 중첩 구조 안에서 `session_accumulated_bytes`/`batch_limit_reached`/`shared_cover`/`conn` 등 상태가 여러 루프 레벨에 걸쳐 공유되고, `sys.exit(10)`이 가장 안쪽 루프 안에서 직접 호출되는 등 진짜 얽힌 제어 흐름을 갖고 있다.
- 이는 기존 로드맵의 B-6(`viewer_txt.js`, TXT/EPUB이 공용 이벤트 핸들러에서 얽혀 있어 분리 보류)과 같은 성격 — 억지로 전체를 쪼개면 회귀 리스크가 실익보다 커진다고 판단해, **핵심 도서 처리 루프(상태 공유 + sys.exit 다발)는 건드리지 않고 그대로 유지**.

대신 상태 공유가 없는(순수 계산/설정로드 성격) 세 블록만 안전하게 분리:
- `_load_lazy_scan_limits()`: 개별 파일 크기 제한 / 세션 누적 한도(MB) 설정 로드 (23줄)
- `_build_scan_targets(db_type, books, library_remote_map)`: DB 1차 후보를 물리 파일 상태까지 점검해 최종 스캔 대상으로 좁히는 순수 필터링 (71줄) — `conn`/누적 상태와 무관
- `_group_targets_by_folder(targets)`: 폴더별 그룹핑 + 자연 정렬 (9줄)

`run_lazy_cover_extraction()` 857→880줄(헬퍼 함수 정의가 파일에 추가돼 총 줄 수는 늘었지만, 함수 자체는 이 3블록만큼 짧아짐). **검증**: `python -m py_compile` 통과, 정규화(`difflib`+집합 비교) 결과 "OLD에만 있는 줄"이 0개로 로직 완전 보존 확인, 새 헬퍼 3개를 실제로 호출해(가짜 book row + 실존 파일 경로) 필터링/그룹핑 결과가 기대대로 동작함을 별도 스모크 테스트로 확인.

**남은 것(의도적으로 손대지 않음)**: 개별 도서 처리 루프(334~563행 상당)는 여전히 하나의 큰 블록 — 세션 누적/배치 한도/graceful exit이 서로 얽혀 있어, 실제 유지보수 불편이 보고되지 않는 한 추가 분리는 하지 않는다. 트랙 E는 이것으로 일단 종료(더 진행할 후보가 남아있지 않음).
