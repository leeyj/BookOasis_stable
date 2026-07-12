# 🧩 메타데이터 플러그인 개발 가이드 (Metadata Plugin Guide)

이 문서는 BookOasis 미디어 서버에서 코어 수정 없이 메타데이터/대시보드 플러그인을 추가하는 최신 규격을 설명합니다.

> 주의: 이 문서는 `plugins/metadata/` 외부 연동 플러그인 가이드입니다. 스캐너 로컬 파서 개발은 [스캐너 파서 개발 가이드](./guide_scanner_parser.md)를 따르십시오.

---

## 1. 핵심 원칙 (중요)

- 코어는 플러그인 고유 이름, 고유 라우트, 내부 함수명을 알지 않습니다.
- 코어는 공통 계약만 사용합니다.
- 플러그인 확장은 플러그인 디렉토리 내부 코드/리소스만으로 끝나야 합니다.

즉, "메인은 이제 플러그인에 관여하지 않는다"가 설계 목표입니다.

---

## 2. 디렉토리 구조 규격

권장 방식은 폴더 기반입니다.

```text
plugins/metadata/
  my_widget/
    __init__.py
    my_widget.py
    index.html      # 선택: 설정 화면 커스텀 UI
    style.css       # 선택: 설정 화면 커스텀 스타일
    script.js       # 선택: 설정 화면 커스텀 스크립트
```

구 방식(단일 파일)도 하위 호환으로 로드되지만, 신규 개발은 폴더 기반을 권장합니다.

빠른 시작 템플릿:

- `plugins/metadata/__template_dashboard_plugin.py`를 복사해 시작
- 파일/폴더명, 클래스명, `id`를 실제 플러그인 이름으로 변경

---

## 3. 플러그인 클래스 기본 계약

모든 플러그인 클래스는 [plugins/metadata/base.py](../plugins/metadata/base.py)를 상속해야 합니다.

필수/권장 필드:

- `id` (str): 고유 식별자
- `name` (str): UI 표시명
- `is_searchable` (bool): 수동 메타데이터 검색 모달 노출 여부
- `config_schema` (list): 설정 폼 스키마
- `dashboard_widget` (dict 또는 None): 대시보드 위젯 메타 (공통 데스크 카드 또는 단독 탭 뷰 구성 정보)

필수 메서드:

- `search(self, db_type, query)`
- `apply(self, db_type, book_id, item_data)`

대시보드 위젯용 공통 메서드:

- `get_dashboard_data(self, db_type, limit=10)`

반환 규격:

- 성공: `{'success': True, 'items': [...]}`
- 실패: `{'success': False, 'error': '...'}`

---

## 4. 설정 UI 및 config_schema

플러그인 설정값은 `settings` 테이블의 `PLUGIN_CONFIG_{id}`에 JSON 문자열로 저장됩니다.

지원 필드 타입:

- `text`, `password`, `number`
- `checkbox`
- `select` (`options` 필요)

예시:

```python
config_schema = [
    {"key": "API_KEY", "label": "API Key", "type": "password", "required": True},
    {"key": "ENABLE_PROXY", "label": "프록시 사용", "type": "checkbox", "default": False},
    {"key": "REGION", "label": "지역", "type": "select", "options": [
        {"value": "kr", "label": "한국"},
        {"value": "us", "label": "미국"}
    ]}
]
```

### 커스텀 설정 UI (선택)

폴더 기반 플러그인에 아래 파일을 추가하면 설정 탭에서 자동 반영됩니다.

- `index.html`: 플러그인 전용 설정 마크업
- `style.css`: 플러그인 전용 스타일
- `script.js`: 플러그인 전용 초기화 로직

---

## 5. 대시보드 위젯 및 플러그인 데스크 계약

독립된 **[플러그인]** 카테고리 화면에 카드를 노출하거나 단독 탭으로 렌더링되기를 원하면 `dashboard_widget`를 정의하고 `get_dashboard_data()`를 구현하십시오.

예시:

```python
dashboard_widget = {
    'title': '신간 위젯',
    'subtitle': '외부 API 신간 목록',
    'provider': 'Example',
    'icon': 'fa-solid fa-book-open',
    'limit': 10,
    'all_desk_tab': True,  # (선택) True 시 공통 데스크 카드가 아닌 단독 전체화면 탭으로 동적 렌더링됨 (기본값: False)
    'supported_types': ['general'],  # (선택) 노출을 허용할 보관함 DB 타입 지정 (생략 시 일반/성인 둘 다 노출)
}

def get_dashboard_data(self, db_type, limit=10):
    # 내부 fetch 헬퍼 호출
    return {'success': True, 'items': []}
```

### 배치 및 정렬 (Sortable.js)
- `'all_desk_tab': False` (혹은 지정 안 함) 상태의 플러그인들은 **[공통 데스크]** 탭 내의 반응형 카드 그리드 리스트에 함께 렌더링됩니다.
- 이 영역의 위젯 카드들은 **마우스 드래그 앤 드롭**을 통해 자유롭게 순서를 바꿀 수 있으며, 브라우저 `localStorage`에 정렬 상태가 보관되어 새로고침 후에도 순서가 유지됩니다.

권장 사항:

- 외부 공개 메서드는 `get_dashboard_data()`만 유지
- 플러그인 내부 구현은 private helper(`_fetch_items`)로 분리

---

## 6. 도서 컨텍스트 메뉴 확장 계약

도서 카드(대시보드/목록/상세 공통)의 컨텍스트 메뉴에 플러그인 항목을 동적으로 노출할 수 있습니다.

플러그인 선택 구현 메서드:

- `get_context_menu_items(self, db_type, context)`
- `run_context_menu_action(self, db_type, action_id, context)`

`get_context_menu_items()` 반환 예시:

```python
def get_context_menu_items(self, db_type, context):
    return [
        {
            'id': 'open_vendor_search',
            'label': '벤더 사이트에서 제목 검색',
            'icon': 'fa-solid fa-up-right-from-square',
        }
    ]
```

`run_context_menu_action()` 반환 규격:

- 성공: `{'success': True, 'message': '...', 'open_url': 'https://...'}`
- 실패: `{'success': False, 'error': '...'}`

프런트 렌더링 메모:

- 컨텍스트 메뉴는 `plugin_name` 기준으로 자동 그룹화되어 섹션/구분선 UI로 출력됩니다.
- 같은 플러그인이 여러 항목을 반환하면 한 그룹 아래로 묶여 표시됩니다.

`context` 기본 필드:

- `book_id`
- `book_title`
- `is_volume_detail`
- `library_id`

코어 관점:

- 코어는 공통 엔드포인트/공통 스키마만 처리
- 실제 메뉴 항목 정의/동작은 플러그인 내부에서만 구현

`stats_dashboard` 컨텍스트 메뉴 예시:

- 항목: `독서 통계 요약 보기`
- 액션: 현재 라이브러리 통계를 조회하여 토스트 메시지로 반환

### 샘플: 네이버 도서 검색 컨텍스트 메뉴

네이버 도서 검색처럼 "현재 책 제목으로 외부 검색 페이지를 여는" 플러그인은 가장 만들기 쉬운 예시입니다. API 키가 필요 없고, 컨텍스트 메뉴 계약만으로 동작합니다.

샘플 파일:

- [plugins/metadata/naver_book/naver_book.py](../plugins/metadata/naver_book/naver_book.py)

핵심 동작:

- `book_id`, `book_title`을 컨텍스트에서 읽습니다.
- 필요하면 `self.get_db_gateway(db_type)`로 `books` 테이블의 최신 `title`, `author`를 다시 조회합니다.
- `run_context_menu_action()`에서 `open_url`을 반환하여 네이버 도서 검색을 새 탭으로 엽니다.

예시 반환값:

```python
{
    'success': True,
    'message': '네이버 도서 검색 페이지를 새 탭으로 엽니다.',
    'open_url': 'https://book.naver.com/search/search.naver?query=...'
}
```

---

## 7. 구현 예시 (간단)

```python
# -*- coding: utf-8 -*-
import json
from plugins.metadata.base import BaseMetadataProvider


class MyWidgetMetadataProvider(BaseMetadataProvider):
    id = "my_widget"
    name = "My Widget"
    is_searchable = False
    config_schema = [{"key": "API_KEY", "label": "API Key", "type": "text", "required": True}]
    dashboard_widget = {
        "title": "My Widget",
        "subtitle": "Demo",
        "provider": "My API",
        "icon": "fa-solid fa-puzzle-piece",
        "limit": 10,
    }

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "대시보드 전용 플러그인입니다."

    def _fetch_items(self, db_type, limit=10):
        return {'success': True, 'items': []}

    def get_dashboard_data(self, db_type, limit=10):
        return self._fetch_items(db_type, limit=limit)
```

### 플러그인 DB 게이트웨이 (권장)

플러그인에서 `import database`로 직접 연결하지 말고, 베이스 헬퍼를 사용하십시오.

- `self.get_db_gateway(db_type)`
- `self.get_plugin_config(db_type, default={})`

게이트웨이 주요 메서드:

- `fetch_one(query, params=())`
- `fetch_all(query, params=())`
- `execute(query, params=())`
- `execute_many(query, seq_of_params)`
- `transaction()`
- `get_setting(key, default=None)` / `set_setting(key, value)`

예시:

```python
def _get_api_key(self, db_type):
    cfg = self.get_plugin_config(db_type, default={})
    return cfg.get("API_KEY")

def _count_books(self, db_type):
    gateway = self.get_db_gateway(db_type)
    row = gateway.fetch_one("SELECT COUNT(*) AS cnt FROM books WHERE COALESCE(is_deleted, 0) = 0")
    return int((row["cnt"] if row else 0) or 0)
```

---

## 8. 등록 및 활성화

1. 플러그인 폴더/파일을 `plugins/metadata/` 아래에 추가합니다.
2. 서버를 재시작합니다.
3. 웹 UI의 환경설정 > 플러그인 설정에서 플러그인을 활성화합니다.
4. 설정값 입력 후 저장합니다.
5. `is_searchable=True`이면 수동 메타데이터 검색 모달에 노출됩니다.
6. `dashboard_widget` + `get_dashboard_data()`를 구현하면 대시보드에 자동 노출됩니다.

---

## 9. 통계 플러그인 예시 (동일 요구사항)

예시 플러그인: `plugins/metadata/stats_dashboard/stats_dashboard.py`

대시보드 노출 항목:

1. 총계: 시리즈 수/도서수
2. 읽은 도서 수(100% 완독 기준): 이번주 00권 / 이번달 00권
3. 신규 추가 수: 이번주 00권 / 이번달 00권

구현 포인트:

- `dashboard_widget`를 정의하여 위젯 카드를 노출
- `get_dashboard_data()`가 위 3개 통계를 `items`로 반환 (주간/월간 동시 집계)
- 코어 수정 없이 플러그인 내부 SQL/로직만으로 확장

참고:

- 이 통계 항목(총계/주간/월간)은 플러그인에서 정의하는 영역입니다.
- 코어는 공통 계약(`dashboard_widget`, `get_dashboard_data`)만 사용하므로, 항목 변경 시 코어 수정이 필요하지 않습니다.

---

## 💡 Tip: iframe 외부 연동 시 보안 제약 사항 안내
독립된 플러그인 화면에서 `<iframe>`을 사용해 외부 웹 서비스를 끌어오고자 할 때는 브라우저 보안 제약에 유의해야 합니다.

1. **X-Frame-Options / CSP 차단**:
   - `X-Frame-Options: SAMEORIGIN` 또는 `Content-Security-Policy` 헤더를 통해 자신들의 사이트가 타사 사이트에 프레임 형태로 삽입되는 것을 차단하는 사이트(예: Google, Naver 등)는 iframe으로 직접 로딩이 불가능합니다.
   - **해결 방안**: 플러그인 파이썬 백엔드(Python)에서 웹 콘텐츠를 직접 `requests`로 긁어온 뒤 보안 헤더를 필터링하여 응답하는 Proxy API를 구축해 프론트엔드로 전달하거나, `target="_blank"` 속성을 지정해 새 창/새 탭으로 바로 열어 주십시오.
2. **Mixed Content 차단**:
   - BookOasis 웹 서비스가 SSL(HTTPS) 환경에서 제공되는 경우, iframe 내에 호출되는 주소 역시 반드시 `https://` 보안 통신 주소여야 합니다. `http://`로 시작하는 일반 주소는 브라우저 보안 규격(Mixed Content)에 의해 자동으로 로드가 완전 차단됩니다.
