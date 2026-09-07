# 홈 대시보드 플러그인화 설계 (초안)

> 상태: **설계 확정(2026-09-07), 계약 스텁(`home_widget`)만 추가됨. 라우트/JS 구현은 미착수.**
> 플러그인 생태계가 계속 늘면서(노래방 플러그인 등장 등) 대시보드에 자기 콘텐츠를 노출하고
> 싶어하는 요청이 늘어난 데서 출발.

## 1. 현재 구조 확인

- `templates/components/views/library_dashboard.html` + `static/js/dashboard.js` (실제 홈 화면 —
  독서 인사이트/최근 읽은 도서/신규 추가 도서)는 **완전히 코어 하드코딩**이며 플러그인 확장
  지점이 전혀 없다.
- 기존 `dashboard_widget` 계약(`plugins/metadata/base.py`, `docs/guide_plugins.md` §5)은 홈이
  아니라 별도의 **[플러그인] 공통 데스크 탭**에 카드를 꽂는 용도다. 이 계약을 확장해도 홈에는
  못 붙는다 — 이름이 비슷해서 혼동하기 쉬운 지점.
- `category_tab` 계약은 사이드바에 완전히 독립된 풀페이지 탭을 만드는 용도로 이미 최고 자유도를
  갖고 있다 (노래방 플러그인이 아마 이 경로로 구현됐을 것).

## 2. 채택 방향: 이원화 전략

1. **기본값은 현행 유지** — 플러그인을 안 쓰는 사용자는 아무 것도 안 변한다.
2. **사용자가 설정에서 켜면** 홈이 "완전 플러그인 배치 화면"으로 전환된다. 이때 코어
   섹션(독서 인사이트/최근 읽은 도서/신규 추가 도서)도 하나의 "빌트인 위젯"으로 래핑되어,
   서드파티 플러그인 위젯과 동일하게 배치 순서를 바꾸거나 숨길 수 있다.

## 3. 새 계약: `home_widget`

`BaseMetadataProvider`에 `dashboard_widget`과 별개 필드로 추가 (구현 완료, `plugins/metadata/base.py`):

```python
home_widget = None
# Example:
# home_widget = {
#     'title': '오늘의 추천곡',
#     'subtitle': 'Karaoke Plugin',
#     'icon': 'fa-solid fa-music',
#     'order': 60,
#     'limit': 10,
#     'sessions': 'all',  # _resolve_plugin_sessions()와 동일 규칙
#     'layout': 'grid',  # 'full'(기본, 1열 전체) | 'grid'(다른 grid 위젯과 한 행에 카드로 배치)
# }
```

**추가 결정(2026-09-07, 4차)**: 홈 화면 레이아웃(카드 순서/폭) 리플로우는 서버사이드 렌더링으로
근본 해결됐지만, 카드 "내용"은 여전히 `get_dashboard_data()`가 응답해야 채워진다 - 플러그인마다
이 메서드가 느리면 그 카드만 로딩 스피너가 오래 남는다(다른 위젯/코어 섹션엔 영향 없음, 이미
병렬 fetch). 코어가 강제할 수 있는 부분이 아니라 플러그인 작성자 책임 영역이라, 코드 변경 대신
`guide_plugins.md`/`guide_plugins_en.md` §5-1에 "느리면 반드시 `self.cache_get`/`cache_set`으로
캐싱하라"는 권고를 추가했다.

**추가 결정(2026-09-07, 3차)**: `layout: 'grid'` 위젯이 전부 동일한 폭이면 위젯마다 콘텐츠
양이 다를 때 불편할 수 있다는 피드백으로, `size`(1/2/3, grid-column span) 필드를 추가했다 -
CSS 한 줄(`grid-column: span N`)만 추가하면 되므로 별도 JS 그룹핑 없이 그대로 확장된다. 개발/검증
단계에서는 size 1/2/3 더미 플러그인 4개(`dummy_grid_widget_a~d`)로 실제 재배치를 테스트했으나,
사용자 환경에 잘못 배포될 경우의 위험을 피하기 위해 배포 전 삭제했다(2026-09-07) — 로컬에서
`layout`/`size`를 확인하려면 `plugins/metadata/`에 임시로 유사한 더미를 새로 만들어 테스트할 것.

**추가 결정(2026-09-07, 2차)**: 최근 읽은 도서/신규 추가 도서(그리고 확장 가능하도록 독서
인사이트 포함) 코어 섹션도 사람마다 불필요하게 느낄 수 있어 플러그인 위젯과 동일하게 ×로
닫을 수 있어야 한다는 피드백 반영 — 코어 섹션도 "+ 위젯 추가" 카탈로그에 다시 나타나 재추가
가능. 이때 코어 섹션의 DOM 래퍼는 절대 제거되지 않고 `display:none`으로만 숨겨지므로(항상
템플릿에 고정 존재), 드래그 재정렬/추가/제거 시 DOM을 그대로 스캔하면 이미 뺀 코어 섹션이
"숨김 상태로 다시 레이아웃에 포함"되며 부활하는 버그가 있었다 — 그래서 프론트는 DOM을 직접
스캔하지 않고 서버가 마지막으로 내려준 "실제 포함 목록"(`lastHomeWidgetOrder`)을 저장/변경의
기준으로 삼는다 (`static/js/dashboard.js`의 `getPresentWidgetOrder()`/`mutateHomeWidgetLayout()`).

**추가 결정(2026-09-07)**: 홈 화면을 `display:flex; flex-direction:column`이 아니라
`display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr))`로 구성해,
`layout: 'full'`인 위젯은 `grid-column: 1 / -1`로 전체 폭을, `layout: 'grid'`인 위젯은 그리드
셀 하나를 차지하게 했다 — 별도 JS 그룹핑 로직 없이 CSS만으로 "1열 전체" vs "카드 그리드"를
위젯별로 선언할 수 있다.

데이터 조회는 기존 `get_dashboard_data(self, db_type, limit=10)`을 재사용한다 — 이미
`dashboard_widget`용으로 구현해둔 플러그인은 필드만 추가하면 홈에도 노출 가능, 신규 메서드
요구 안 함.

## 4. 코어 섹션의 "빌트인 위젯"화

실제 렌더링 로직(시리즈 스크롤, 세션별 라벨, 독서 인사이트 위젯 로딩)은 그대로 두고,
**레이아웃 계층에서만** 다음 고정 id로 등록:

| id | 소스 |
|---|---|
| `core.reading_insights` | `dashboard_reading_insights.html` + `loadDashboardInsights()` |
| `core.recent` | `dashboard-history-row` + `renderDashboardHistory` |
| `core.new` | `dashboard-new-row` + `renderDashboardRecentlyAdded` |

이 3개는 하드코딩된 상수 목록으로 취급하고, 플러그인처럼 DB에서 discover하지 않는다.

## 5. 레이아웃 저장

기존 `user_settings` key-value 테이블(`repositories/*/settings_repository.py`, 프론트
`api.updateUserSetting()` — `my_settings_tab.html`의 `DETAIL_VOLUME_GRID_VIEW`와 동일 패턴)을
그대로 재사용한다. 새 DB 마이그레이션 불필요.

- `HOME_DASHBOARD_MODE`: `'classic'`(기본) | `'plugin'`
- `HOME_WIDGET_LAYOUT`: JSON 배열, 예:
  ```json
  [
    {"id": "core.reading_insights", "hidden": false},
    {"id": "core.recent", "hidden": false},
    {"id": "plugin_karaoke", "hidden": false},
    {"id": "core.new", "hidden": false}
  ]
  ```
  최초 진입(저장된 레이아웃 없음) 시 기본값 = **코어 3개만**(현재 순서). 활성 `home_widget`
  플러그인은 자동으로 끼워 넣지 않는다 — 설치된 플러그인이 늘어날수록 원치 않는 위젯까지
  전부 노출되는 걸 막기 위해, 사용자가 "+ 위젯 추가" 카탈로그에서 명시적으로 고른 플러그인만
  레이아웃에 들어간다(2026-09-07 결정). 반대로 코어 3개는 저장된 레이아웃에 없어도 항상
  자동 삽입된다(신규 코어 섹션 추가 대비).

## 6. 백엔드 API

`api/routes/plugin_routes.py`에 신규 엔드포인트 1개만 추가 (기존
`/api/media/dashboard/widgets/<id>/data`는 그대로 재사용):

```
GET /api/media/home-layout?type=<db_type>
```
- 로그인 사용자의 `HOME_DASHBOARD_MODE`, `HOME_WIDGET_LAYOUT` 조회
- `home_widget`을 선언하고 활성화된 플러그인을 `MetadataFactory.get_available_providers()`에서
  추출, `_resolve_plugin_sessions()`로 세션 필터링 (기존 `category-plugins` 엔드포인트와 동일
  패턴)
- 저장된 레이아웃과 병합해 최종 순서/숨김 배열(`widgets`) 반환
- 아직 레이아웃에 없는(=추가 안 한) 활성 플러그인 위젯 목록을 `catalog`로 함께 반환 —
  프론트의 "+ 위젯 추가" 버튼 그룹이 이 목록을 그린다. 추가/제거는 별도 엔드포인트 없이
  `HOME_WIDGET_LAYOUT` 사용자 설정을 다시 저장하는 것으로 처리한다 (`static/js/dashboard.js`의
  `mutateHomeWidgetLayout()`).

레이아웃 저장(순서 변경/숨김 토글)은 새 엔드포인트 없이 기존 사용자 설정 저장 경로
(`api.updateUserSetting`)로 `HOME_WIDGET_LAYOUT` 키만 갱신하면 된다.

## 7. 프론트엔드

- `templates/components/settings/general_tab.html` + `static/js/settings/general.js`: "홈 화면을
  플러그인 배치 모드로 전환" 체크박스 1개 추가, `DETAIL_VOLUME_GRID_VIEW`와 동일한 읽기/저장
  흐름.
- `dashboard.js`: `HOME_DASHBOARD_MODE === 'plugin'`이면 기존 고정 마크업 대신,
  `/api/media/home-layout` 결과 순서대로 위젯 컨테이너를 동적 생성 — 코어 3개는 기존 렌더
  함수 그대로 재사용(껍데기 컨테이너만 동적 위치로 이동), 플러그인 위젯은 desk-tab에서
  이미 쓰는 카드 렌더링 코드를 재사용해 `get_dashboard_data()` 결과를 그린다.
- 순서 변경 UI는 desk-tab에 이미 있는 Sortable.js 드래그 정렬을 재사용하되, 결과를
  `localStorage`가 아니라 `HOME_WIDGET_LAYOUT` 사용자 설정에 저장한다 (다기기 동기화를 위해 —
  desk-tab 카드 정렬과 달리 "내 홈 화면"이라 기기 간 일관성이 중요).

## 8. 문서화

`docs/guide_plugins.md`에 §5 뒤로 새 절 추가 예정: `dashboard_widget`(데스크 탭/단독 탭) vs
`home_widget`(사용자가 켠 경우에만 실제 홈에 노출)의 차이를 명확히 구분 — 두 계약이 이름이
비슷해서 플러그인 개발자가 헷갈리기 쉬움.

## 9. 호환성 / 거버넌스

- 기존 ~100개 플러그인이 의존하는 `category_tab`/`dashboard_widget`/`get_dashboard_data`
  계약은 전혀 건드리지 않음 — `home_widget`은 완전히 새로운 선택적 필드.
- `HOME_DASHBOARD_MODE` 기본값이 `'classic'`이므로 아무도 설정을 건드리지 않으면 현재 동작과
  100% 동일.

## 10. 다음 단계 (미착수)

1. `/api/media/home-layout` 라우트 구현
2. `general_tab.html`/`general.js`에 모드 토글 UI
3. `dashboard.js`에 plugin 모드 렌더링 + Sortable.js 드래그 저장
4. `docs/guide_plugins.md` §5 뒤 신규 절 추가
5. 샘플 플러그인 하나(`sample_plugins/metadata/`)에 `home_widget` 예시 적용해 수동 검증:
   (a) `HOME_DASHBOARD_MODE` 미설정 계정 홈 화면이 기존과 동일한지, (b) 플러그인 모드 켠 뒤
   `home_widget` 없는 계정도 코어 3위젯이 정상 렌더되는지, (c) 순서 변경·숨김·세션 필터링 동작.
