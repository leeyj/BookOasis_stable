# 🧩 플러그인 개발 가이드 (Metadata Plugin Guide)

이 문서는 BookOasis 미디어 서버에서 코어 수정 없이 메타데이터/대시보드 플러그인을 추가하는 최신 규격을 설명합니다.

> 주의: 이 문서는 `plugins/metadata/` 외부 연동 플러그인 가이드입니다. 스캐너 로컬 파서 개발은 [스캐너 파서 개발 가이드](./guide_scanner_parser.md)를 따르십시오.

---

## 1. 핵심 원칙 (중요)

- 코어는 플러그인 고유 이름, 고유 라우트, 내부 함수명을 알지 않습니다.
- 코어는 공통 계약만 사용합니다.
- 플러그인 확장은 플러그인 디렉토리 내부 코드/리소스만으로 끝나야 합니다.

즉, "메인은 이제 플러그인에 관여하지 않는다"가 설계 목표입니다.

### 호환성 매트릭스 (코어 ↔ 플러그인 계약)

| 코어 버전 범위 | 필수 계약 | 선택 계약 | 비고 |
| :--- | :--- | :--- | :--- |
| 1.0.0 ~ 1.0.4 | `search`, `apply` | `dashboard_widget`, `get_dashboard_data` | 폴더 기반/단일 파일 모두 허용 |
| 1.0.5 ~ 1.0.6 | `search`, `apply` | `get_context_menu_items`, `run_context_menu_action`, `update_manifest` | 컨텍스트 메뉴/샘플 업데이트 지원 |
| 1.0.7+ (현재) | `search`, `apply` | `on_scan_new_books_detected`, `dispatch_webhook`, `update_manifest` | 표준 이벤트 웹훅(`book.new/read/finish`) 병행 운영 권장 |

호환성 원칙:

- 코어는 **필수 계약**만 보장합니다.
- 선택 계약은 코어 버전에 따라 미지원일 수 있으므로, 플러그인 내부에서 기능 감지(fallback) 처리하는 것을 권장합니다.

---

## 2. 디렉토리 구조 규격

권장 방식은 폴더 기반입니다.

```text
plugins/metadata/
  my_widget/
    __init__.py
    my_widget.py
        VERSION         # 필수(자동 업데이트 지원 대상인 경우)
    index.html      # 선택: 설정 화면 커스텀 UI
    style.css       # 선택: 설정 화면 커스텀 스타일
    script.js       # 선택: 설정 화면 커스텀 스크립트
```

### 자동 업데이트 지원용 버전 파일 규격 (필수)

GitHub 기반 플러그인 자동 업데이트 지원 대상으로 등록하려면, 플러그인 루트에 `VERSION` 파일을 두고 아래 키를 반드시 포함해야 합니다.

```json
{
    "plugin version": "1.0.0"
}
```

정책:

- 키 이름은 반드시 `plugin version` (공백 포함)
- 값은 SemVer 형식 권장 (`MAJOR.MINOR.PATCH`)
- 이 값이 없으면 자동 업데이트 지원 대상에서 제외
- 구 키(`plugin_version`)는 하위 호환 파싱 대상이지만 신규/공식 규약은 `plugin version`만 사용

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
- `update_manifest` (dict 또는 None): 플러그인 내부 업데이트 선언 계약

필수 메서드:

- `search(self, db_type, query)`
- `apply(self, db_type, book_id, item_data)`

대시보드 위젯용 공통 메서드:

- `get_dashboard_data(self, db_type, limit=10)`

반환 규격:

- 성공: `{'success': True, 'items': [...]}`
- 실패: `{'success': False, 'error': '...'}`

### 플러그인 내부 업데이트 계약 (`update_manifest`)

업데이트 버튼 노출/실행 규칙은 코어 하드코딩이 아니라, **각 플러그인 클래스 내부의 `update_manifest` 선언**으로 동작합니다.

예시 (`stats_dashboard` 방식):

```python
update_manifest = {
    "enabled": True,
    "provider": "github-raw",
    "raw_base_url": "https://raw.githubusercontent.com/<org>/<repo>/<branch>/plugins/metadata/<plugin_id>",
    "files": ["<plugin_module>.py", "__init__.py", "VERSION"],
    "version_file": "VERSION",
    "version_key": "plugin version",
    "show_sample_update_button": True,
}
```

필드 설명:

- `enabled`: 업데이트 기능 사용 여부
- `provider`: 현재 `github-raw`만 지원
- `raw_base_url`: 플러그인 파일 원본 경로
- `files`: 업데이트 시 교체할 파일 목록
- `version_file`: 버전 파싱 대상 파일
- `version_key`: 버전 JSON 키 (권장: `plugin version`)
- `show_sample_update_button`: 환경설정 화면에 샘플 업데이트 버튼 노출 여부

실행 정책:

- 업데이트는 `현재 버전 < GitHub 버전`일 때만 허용
- `raw_base_url/files`가 GitHub에 아직 없으면 404가 정상이며, 푸시 이후 재시도

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

### 웹훅 연동 (최신 권장 방식)

최신 권장 방식은 `.env`가 아니라 **플러그인 설정 화면**에서 웹훅 대상을 구성하는 것입니다.

추가로 스캐너는 신규 도서를 감지하면 자동으로 `scan.new_books_detected` 이벤트를 발송합니다.

- payload: `db_type`, `library_id`, `library_name`, `new_books_count`, `sample_titles`

### 신규도서 웹훅 알림 예제 플러그인

- 경로: `plugins/metadata/webhook_new_books_notify/webhook_new_books_notify.py`
- 동작: 스캔 완료 후 신규 도서가 있으면 `on_scan_new_books_detected` 훅에서 설정된 다중 웹훅 대상으로 전송
- 지원 포맷: `discord`, `slack`, `telegram`, `generic`, `custom`
- 참고: `.env` 없이 플러그인 설정만으로 동작합니다.

사용 방법:

1. 환경설정 > 플러그인 설정에서 `신규도서 웹훅 알림` 활성화
2. `ENABLE_SCAN_WEBHOOK_NOTIFY=true` 저장
3. `WEBHOOK_TARGETS_JSON` 입력
4. (선택) `CUSTOM_EVENT_PAYLOAD_JSON`, `MAX_SAMPLE_TITLES`, `REQUEST_TIMEOUT_SEC` 조정
5. 라이브러리 스캔 실행

테스트 URL 빠른 검증:

1. `https://webhook.site` 접속 후 임시 수신 URL 발급
2. 아래처럼 `WEBHOOK_TARGETS_JSON`에 테스트 타깃 추가
3. 스캔 실행 후 webhook.site 수신 로그에서 요청 본문(JSON) 확인

```json
[
    {
        "name": "webhook-site-test",
        "url": "https://webhook.site/your-uuid",
        "format": "generic",
        "method": "POST"
    }
]
```

응답 판별 테스트(httpbin):

```json
[
    {
        "name": "httpbin-ok",
        "url": "https://httpbin.org/post",
        "format": "custom",
        "method": "POST",
        "body": {
            "ok": true,
            "event": "{{event}}",
            "count": "{{new_books_count}}"
        },
        "success_path": "json.ok"
    }
]
```

주의: 테스트 URL에는 토큰/개인정보가 포함된 실제 운영 payload를 보내지 마십시오.

### 표준 이벤트 웹훅 스키마 (book.new / book.read / book.finish)

커뮤니티 연동용 표준 이벤트 웹훅은 아래 형태를 권장합니다.

- Endpoint: `POST http://<server>/webhook`
- Event: `book.new`, `book.read`, `book.finish`
- 공통 최상위 키: `event`, `user`, `Account`, `Metadata`

예시:

```json
{
    "event": "book.read",
    "user": true,
    "Account": {
        "id": 123456,
        "title": "사용자이름"
    },
    "Metadata": {
        "type": "book",
        "format": "epub",
        "title": "책 제목",
        "author": "저자 이름",
        "publisher": "출판사",
        "series": "시리즈 명",
        "seriesIndex": null,
        "progress": 45,
        "totalPages": null,
        "currentLocation": "epubcfi(/6/2[chap01]!/4/2/14)",
        "addedAt": 1690000000
    }
}
```

포맷 제약(중요):

- EPUB/TXT는 물리 페이지가 고정되지 않으므로 `totalPages`는 `null`일 수 있습니다.
- 이 경우 진행률은 `progress`(0~100 퍼센트)를 기준으로 처리하십시오.
- `currentLocation`은 포맷별 포인터로 해석하십시오.
    - EPUB: `href`/`cfi`/`spine` 기반 문자열
    - TXT: `chunk:N` 형태
    - 고정 페이지 포맷(PDF/ZIP/CBZ): `page:N` 형태

권장 소비 정책:

- 완독 판정은 `progress` 또는 `book.finish` 이벤트를 우선 사용
- `totalPages`는 보조 정보로만 사용

### 표준 이벤트 전송 환경변수

코어 표준 이벤트 웹훅은 아래 환경변수로 제어합니다.

- `WEBHOOK_EVENT_ENDPOINT` 또는 `WEBHOOK_EVENT_ENDPOINTS`
- `WEBHOOK_EVENT_TIMEOUT`
- `WEBHOOK_EVENT_RETRY`
- `WEBHOOK_EVENT_SECRET` (HMAC 서명, 헤더: `X-BookOasis-Signature`)

참고:

- 기존 `WEBHOOK_TARGETS_JSON` 기반 플러그인 방식과 병행 가능합니다.
- 표준 이벤트는 플러그인 제작자가 공통 계약만으로 수신 로직을 구현할 수 있도록 설계되었습니다.

---

## 7. 플러그인 개발자 릴리즈 절차 (자동 업데이트 포함)

1. 플러그인 코드 변경 후 `VERSION`의 `plugin version`을 증가
2. 플러그인 클래스의 `update_manifest` 경로/파일 목록이 실제 리포지토리와 일치하는지 점검
3. GitHub에 push 후 `raw_base_url`에서 파일 직접 열람(404 해소 확인)
4. 환경설정 > 플러그인 설정에서 샘플 업데이트 버튼 실행
5. `현재 < GitHub` 조건에서만 업데이트되는지, 동일/낮은 GitHub 버전에선 차단되는지 검증

`WEBHOOK_TARGETS_JSON` 예시:

```json
[
    {
        "name": "discord-main",
        "url": "https://discord.com/api/webhooks/...",
        "format": "discord"
    },
    {
        "name": "telegram-main",
        "url": "https://api.telegram.org/bot<token>/sendMessage",
        "format": "telegram",
        "chat_id": "123456789"
    },
    {
        "name": "ops-custom",
        "url": "https://example.com/hook",
        "format": "custom",
        "method": "POST",
        "headers": {
            "Authorization": "Bearer YOUR_TOKEN"
        },
        "body": {
            "event": "{{event}}",
            "library": "{{library_name}}",
            "count": "{{new_books_count}}",
            "titles": "{{sample_titles_csv}}"
        },
        "success_path": "ok"
    }
]
```

`success_path`를 설정하면 응답 JSON에서 해당 경로가 truthy일 때만 성공으로 판정합니다.
(예: `ok`, `result.success`)

---

## 7. 구현 예시 (간단)

아래 두 예시는 AI/사람 모두가 복사해 바로 실행하기 쉬운 최소 샘플입니다.

### 예시 A: 검색형 메타데이터 플러그인 (최소)

```python
# -*- coding: utf-8 -*-
from plugins.metadata.base import BaseMetadataProvider


class DemoSearchMetadataProvider(BaseMetadataProvider):
    id = "demo_search"
    name = "Demo Search"
    is_searchable = True
    config_schema = []

    def search(self, db_type, query):
        q = str(query or '').strip()
        if not q:
            return {'success': True, 'items': []}
        return {
            'success': True,
            'items': [
                {
                    'title': q,
                    'author': 'Unknown',
                    'publisher': '',
                    'summary': 'Demo search result',
                }
            ]
        }

    def apply(self, db_type, book_id, item_data):
        # 실제 플러그인은 게이트웨이로 books UPDATE 처리
        return True, 'demo applied'
```

### 예시 B: 대시보드 위젯 플러그인 (최소)

```python
# -*- coding: utf-8 -*-
import json
from plugins.metadata.base import BaseMetadataProvider


class MyWidgetMetadataProvider(BaseMetadataProvider):
    id = "my_widget"
    name = "My Widget"
    is_searchable = False
    config_schema = [{"key": "API_KEY", "label": "API Key", "type": "text", "required": True}]
    update_manifest = {
        "enabled": True,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/<org>/<repo>/<branch>/plugins/metadata/my_widget",
        "files": ["my_widget.py", "__init__.py", "VERSION"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": True,
    }
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

업데이트 지원 플러그인이라면 위 예시처럼 `update_manifest`를 클래스 내부에 선언하고,
`VERSION` 파일에 `"plugin version"` 키를 함께 유지하십시오.

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
