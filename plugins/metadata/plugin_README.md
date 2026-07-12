# Metadata Provider Plugin Guide (메타데이터 프로바이더 플러그인 개발 가이드)

This directory is designed for pluggable metadata providers. You can create a new plugin to support metadata search in other countries (e.g., USA, Japan, etc.) or add new UI widgets without modifying the core system.

이 디렉토리는 플러그형 메타데이터 프로바이더를 위해 설계되었습니다. 코어 소스코드를 수정하지 않고도 외부 API(예: Google Books, Amazon 등)를 연동하는 새 플러그인을 개발하여 붙일 수 있습니다.

---

## How to Create a New Plugin (새 플러그인 추가 방법)

### 1. Create a provider module (프로바이더 모듈 생성)
You can use either legacy single-file style or folder-based style.

다음 2가지 방식 중 하나를 사용할 수 있습니다.

- Legacy single-file: `plugins/metadata/google.py`
- Folder-based (recommended): `plugins/metadata/google/google.py`

For folder-based plugins, this loader also supports optional UI assets:

- `plugins/metadata/google/index.html` (custom settings UI)
- `plugins/metadata/google/style.css` (plugin-specific styles)
- `plugins/metadata/google/script.js` (optional initializer script)

### 2. Implement the provider class (프로바이더 클래스 구현)
Your class must inherit from `BaseMetadataProvider` defined in [base.py](base.py).
The class name must follow this pattern: `{CamelCaseFileName}MetadataProvider`.

작성할 클래스는 반드시 `plugins/metadata/base.py`에 정의된 `BaseMetadataProvider`를 상속받아야 합니다.
클래스 이름은 `{파일명의CamelCase}MetadataProvider` 형태를 권장합니다. (예: `GoogleMetadataProvider`)

하위 호환을 위해 기존 방식(`Aladin_newMetadataProvider`)도 여전히 로드됩니다.

### 3. Define UI & Configuration Properties (UI 및 설정 속성 정의)
To make your plugin configurable from the Web UI (Settings > Plugin Settings), define the following class attributes:

웹 UI(환경설정 > 플러그인 설정)에 플러그인이 노출되고 구성될 수 있도록 다음 속성을 정의해야 합니다:
- `id` (str): Unique identifier (usually the same as the filename). / 고유 식별자 (보통 파일명과 동일하게 설정)
- `name` (str): The plugin name displayed to users. / 사용자에게 보여질 플러그인 이름
- `is_searchable` (bool): Whether to show this plugin in the manual metadata matching search modal. / 도서 수동 매칭 검색 모달에 이 플러그인을 노출할지 여부
- `config_schema` (list): Defines the specification of fields to be inputted in the UI. / UI에서 입력받을 필드들의 규격을 정의합니다.

#### 💡 Complex Configuration Storage & Retrieval (JSON Serialization) / 복잡한 설정 값 저장 및 불러오기
This system serializes the form data defined in `config_schema` into a **single JSON string and stores it in the DB**. Therefore, no matter how complex the data structure is (such as dropdowns, boolean checkboxes, multiple inputs, etc.), it can be stored and retrieved without data loss.

이 시스템은 `config_schema`에 정의된 폼 데이터를 **단일 JSON 문자열로 직렬화하여 DB에 저장**합니다. 따라서 단순 텍스트뿐만 아니라 드롭다운, 불리언 체크박스, 다중 입력 등 아무리 복잡한 데이터 구조라도 손실 없이 저장하고 불러올 수 있습니다.

**Supported `type` kinds and examples (지원되는 `type` 종류 및 예시):**
- `text`, `password`, `number`: Basic text and number input forms / 기본적인 텍스트 및 숫자 입력 폼
- `checkbox`: Boolean (True/False) switch form / 불리언(True/False) 스위치 폼
- `select`: Dropdown selection form (Requires adding an `options` array) / 드롭다운 선택 폼 (이 경우 `options` 배열 추가 필요)

**Complex Form Definition Example (복잡한 폼 정의 예시):**
```python
config_schema = [
    {"key": "API_KEY", "label": "API Token", "type": "password", "required": True},
    {"key": "MAX_RETRIES", "label": "Max Retries", "type": "number", "default": 3},
    {"key": "ENABLE_PROXY", "label": "Enable Proxy", "type": "checkbox", "default": False},
    {"key": "SERVER_REGION", "label": "Server Region", "type": "select", "options": [
        {"value": "us-east", "label": "US East"},
        {"value": "ap-northeast", "label": "Asia Pacific (Seoul)"}
    ]}
]
```
If defined as above, the frontend automatically renders the composite form, and upon saving, it is converted into a JSON object like `{"API_KEY": "...", "MAX_RETRIES": 3, "ENABLE_PROXY": false, "SERVER_REGION": "ap-northeast"}` and safely stored as a string in the `value` column of the `settings` table. When retrieving, you can restore it directly into a Python dictionary using `json.loads()`.

위와 같이 정의하면 프론트엔드가 자동으로 복합 폼을 렌더링하며, 저장 시 `{"API_KEY": "...", "MAX_RETRIES": 3, "ENABLE_PROXY": false, "SERVER_REGION": "ap-northeast"}` 형태의 예쁜 JSON 객체로 변환되어 `settings` 테이블의 `value` 컬럼에 문자열로 안전하게 저장됩니다. 불러올 때는 템플릿의 `json.loads()`를 통해 파이썬 딕셔너리로 바로 복원하여 꺼내 쓸 수 있습니다.

### 4. Implement required methods (필수 메서드 구현)
You need to implement the following two methods:
- `search(self, db_type, query)`: Search external API and return a list of dictionaries.
- `apply(self, db_type, book_id, item_data)`: Download covers and update the database.

### 5. Dashboard Widget Contract (대시보드 위젯 계약)
If you want to expose a plugin widget on the plugins desk category screen, implement the contract below.

플러그인 카테고리 화면에 플러그인 위젯을 표시하려면 아래 계약을 구현하세요.

- Class attribute `dashboard_widget` (dict)
    - Keys: `title`, `subtitle`, `provider`, `icon`, `limit`
    - `all_desk_tab` (bool, Optional):
        - `True`: Renders the plugin as an exclusive full-screen tab instead of a grid card on the common desk.
        - `False` (or omitted): Renders the plugin inside the **[Common Desk]** responsive grid. Cards in the common desk support drag-and-drop sorting via `Sortable.js` (layout order preserved in `localStorage`).
        - `True` 설정 시, 공통 데스크의 그리드 카드로 들어가지 않고 상단에 전용 탭이 동적으로 추가되어 100% 가로폭 단독 화면으로 렌더링됩니다.
        - `False` (혹은 생략) 시, **[공통 데스크]** 반응형 그리드에 카드로 배치되며 `Sortable.js`를 이용한 마우스 드래그 정렬을 기본 지원합니다. (정렬 순서는 `localStorage`에 자동 영구 저장)
    - `supported_types` (list, Optional):
        - Example: `["general", "adult"]`
        - Specifies which library database types (general/adult) this widget is allowed to render on. If omitted, the widget displays on both libraries by default.
        - 노출을 허용할 보관함 DB 타입의 리스트입니다. 생략 시 기본적으로 일반 도서와 성인 도서 화면 둘 다 노출됩니다.
- Method `get_dashboard_data(self, db_type, limit=10)`
    - Must return JSON-like dict in this shape:
        - Success: `{'success': True, 'items': [...]}`
        - Failure: `{'success': False, 'error': '...'}`

Important:
- The core no longer knows plugin-specific names or routes.
- The core only discovers `dashboard_widget` metadata and calls `get_dashboard_data`.
- Therefore, plugin-specific helper names (e.g. `_fetch_new_releases`) should remain internal/private.

Quick start template:
- Copy `plugins/metadata/__template_dashboard_plugin.py`
- Rename to your plugin file/folder module (for example `plugins/metadata/my_widget/my_widget.py`)
- Update class name, `id`, `name`, `config_schema`, `dashboard_widget`, and `_fetch_items()`
- Restart server and enable plugin in Settings > Plugin Settings

---

## Example Template (최신 예시 템플릿)

다음은 UI 연동 및 DB 설정값 불러오기가 모두 포함된 완벽한 미국 Google Books API 플러그인 예시입니다.

```python
# -*- coding: utf-8 -*-
import os
import json
import database
from plugins.metadata.base import BaseMetadataProvider

class GoogleMetadataProvider(BaseMetadataProvider):
    """
    US Google Books API Metadata Provider Example.
    """
    id = "google"
    name = "구글 도서 검색"
    is_searchable = True
    config_schema = [
        {
            "key": "GOOGLE_API_KEY", 
            "label": "Google API Key", 
            "type": "text", 
            "required": True, 
            "description": "구글 도서 검색 API를 사용하기 위한 인증 키입니다."
        }
    ]

    def _get_api_key(self, db_type):
        """웹 UI에서 사용자가 입력하여 DB에 저장된 API Key를 불러오는 헬퍼 메서드"""
        api_key = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'PLUGIN_CONFIG_google'")
            row = cursor.fetchone()
            if row and row['value']:
                config = json.loads(row['value'])
                api_key = config.get('GOOGLE_API_KEY')
            conn.close()
        except Exception:
            pass
        return api_key

    def search(self, db_type, query):
        api_key = self._get_api_key(db_type)
        if not api_key:
            return [] # API 키가 없으면 검색 중단
            
        if not query:
            return []
        
        # TODO: Implement Google Books API request here using `api_key`.
        # Format the results into the following structure:
        results = [
            {
                'title': 'Example Book Title',
                'author': 'Author Name',
                'publisher': 'Publisher Name',
                'pubDate': '2026-01-01',
                'cover': 'https://example.com/cover.jpg',
                'description': 'This is a description of the book.',
                'link': 'https://books.google.com/example'
            }
        ]
        return results

    def apply(self, db_type, book_id, item_data):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        try:
            # 1. Fetch current details
            cursor.execute("SELECT file_path, library_id FROM books WHERE id = ?", (book_id,))
            book = cursor.fetchone()
            if not book:
                conn.close()
                return False, '도서를 찾을 수 없습니다.'
                
            # 2. Download and Save cover image
            cover_filename = None
            if item_data.get('cover'):
                # 이미지 다운로드 및 로컬 캐싱 로직 구현...
                pass
                
            # 3. Update database
            cursor.execute("""
                UPDATE books
                SET author = ?, publisher = ?, summary = ?, link = ?,
                    cover_image = COALESCE(NULLIF(?, ''), cover_image),
                    cover_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                item_data.get('author', ''),
                item_data.get('publisher', ''),
                item_data.get('description', ''),
                item_data.get('link', ''),
                cover_filename,
                book_id
            ))
            
            conn.commit()
            conn.close()
            return True, f'"{item_data.get("title")}" 메타데이터가 적용되었습니다!'
        except Exception as e:
            if conn:
                conn.close()
            return False, f'Error: {str(e)}'
```

---

## How to Enable the Plugin (플러그인 활성화 방법)

In the past, you had to modify `METADATA_PROVIDER` in the `.env` file, but in the latest architecture, everything is controlled from the Web Browser UI.

과거에는 `.env` 파일의 `METADATA_PROVIDER`를 수정해야 했으나, 최신 아키텍처에서는 웹 브라우저 UI에서 모든 것을 제어합니다.

1. Write the code and save it in the `plugins/metadata/` folder. (코드를 작성하여 `plugins/metadata/` 폴더에 저장합니다.)
2. Restart the media server. (미디어 서버를 재시작합니다.)
3. Access the **Settings > Plugin Settings** tab in the Web UI, and your written plugin will be automatically displayed. (웹 UI의 **환경설정 > 플러그인 설정** 탭에 접속하면 작성하신 플러그인이 자동으로 표시됩니다.)
4. **Enable (ON)** the plugin in that tab, enter configuration values like API Keys, and save. (해당 탭에서 플러그인을 **활성화(ON)**하고 API Key 등의 설정값을 입력한 뒤 저장합니다.)

If your plugin provides `index.html` and `style.css`, the plugin settings tab will render that custom UI automatically. (`index.html`, `style.css`가 있으면 설정 탭에서 플러그인 전용 UI가 자동 렌더링됩니다.)
5. Plugins with `is_searchable = True` will automatically be added as a dropdown option in the "Manual Metadata Matching" search modal on the book details page. (`is_searchable = True`인 플러그인들은 도서 상세 보기의 "수동 메타데이터 매칭" 검색 모달에 드롭다운 옵션으로 자동 추가됩니다.)

### Sample: Naver Book Search Context Menu (샘플: 네이버 도서 검색 컨텍스트 메뉴)

If you only want to add a quick external search action for the current book, use the context menu contract. This is a good starter example for community plugins because it does not require any external API key.

현재 도서에 대해 외부 검색만 빠르게 열고 싶다면 컨텍스트 메뉴 계약을 사용하세요. 이 방식은 API 키가 필요 없어서 커뮤니티 샘플로 적합합니다.

Example file:

- `plugins/metadata/naver_book/naver_book.py`

Key behavior:

- Reads `book_id` and `book_title` from the context payload
- Optionally loads the latest `title` and `author` from DB via `self.get_db_gateway(db_type)`
- Returns `open_url` to open `https://book.naver.com/search/search.naver?query=...`

핵심 동작:

- 컨텍스트 payload의 `book_id`, `book_title`을 읽습니다.
- 필요하면 `self.get_db_gateway(db_type)`로 DB에서 최신 `title`/`author`를 다시 읽습니다.
- `open_url`을 반환하여 `https://book.naver.com/search/search.naver?query=...`를 새 탭으로 엽니다.

Recommended pattern:

```python
class NaverBookMetadataProvider(BaseMetadataProvider):
    id = "naver_book"
    name = "네이버 도서 검색"
    is_searchable = False

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "..."

    def get_context_menu_items(self, db_type, context):
        return [{"id": "open_naver_book_search", "label": "네이버 도서에서 검색", "icon": "fa-solid fa-book-open"}]

    def run_context_menu_action(self, db_type, action_id, context):
        ...
```

---

### 💡 Tip: Handling iframe Security Constraints (iframe 보안 제약 사항 처리 팁)
When displaying external web content inside a custom plugin dashboard via `<iframe>`, you may encounter loading failures due to security policies.
커스텀 플러그인 화면에서 `<iframe>`을 이용해 외부 웹 사이트를 렌더링할 때, 보안 헤더 제약으로 인해 페이지 로딩이 실패할 수 있습니다.

1. **X-Frame-Options / CSP (Content Security Policy)**:
   - Many websites set `X-Frame-Options: SAMEORIGIN` or `Content-Security-Policy: frame-ancestors` headers (e.g. Google, Naver, GitHub) to prevent clickjacking. These sites **cannot** be rendered inside an iframe directly.
   - 클릭재킹 방지를 위해 `X-Frame-Options: SAMEORIGIN` 등이 선언된 메이저 웹 사이트들은 브라우저 수준에서 iframe 렌더링이 차단됩니다.
   - **Solution**: Implement a reverse proxy route in your plugin's python backend to fetch the HTML, strip out the restrictive headers, and return it to the frontend iframe. Or, simply use `target="_blank"` to open it in a new tab.
   - **해결책**: 플러그인 파이썬 백엔드에서 외부 웹페이지를 `requests` 등으로 읽어 들여 헤더를 거르고 중계해주는 Proxy API를 만들거나, `target="_blank"` 속성을 사용해 새 창으로 링크아웃 처리하십시오.

2. **Mixed Content**:
   - If the BookOasis server runs on HTTPS, any iframe URL must also use `https://`. Unencrypted `http://` resources will be blocked by browsers.
   - BookOasis 미디어 서버가 HTTPS 프로토콜로 작동하고 있는 경우, iframe의 src 주소 역시 반드시 `https://` 보안 통신 주소여야 로드됩니다. (`http://`는 Mixed Content 차단 대상)

