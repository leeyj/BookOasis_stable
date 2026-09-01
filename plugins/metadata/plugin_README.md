# 🧩 Metadata Provider Plugin Guide (메타데이터 프로바이더 플러그인 개발 가이드)

이 문서는 BookOasis 미디어 서버에서 코어 소스코드 수정 없이 메타데이터 프로바이더, 대시보드 위젯, 카테고리 레벨 커스텀 뷰포트, 그리고 이벤트 웹훅 플러그인을 추가하는 **최신 1.0.7+ 규격**을 설명합니다.

> 💡 **참고**: 스캐너 로컬 파서 개발은 [스캐너 파서 개발 가이드](../../docs/guide_scanner_parser.md)를 참조하십시오.

> ⚠️ **이 `plugins/metadata/` 폴더는 `docker-compose.yml`에서 호스트에 바인드 마운트되는 사용자 데이터 폴더입니다.** 여기에는 프레임워크 필수 파일(`base.py`, `__init__.py`, 템플릿)만 두고, 저장소가 기본 제공하는 예시 플러그인은 `sample_plugins/metadata/`(마운트되지 않는 별도 위치)에 보관합니다. 업데이트(`git pull`, `git clean` 등) 과정에서 사용자가 직접 설치한 플러그인이 유실되지 않도록 하기 위함입니다. 저장소 기본 샘플을 쓰고 싶다면 [설정] > [플러그인] 탭의 **"샘플에서 설치"** 버튼을 이용하세요.

---

## 1. 핵심 원칙 (Core Principles)

- **독립성 (Loose Coupling)**: 북오아시스 코어는 플러그인 고유 이름, 고유 라우트, 내부 함수명을 직접 알지 않고 공통 계약(Contract)만을 이용해 동적으로 연동됩니다.
- **자폐성 (Self-containment)**: 플러그인 확장은 `plugins/metadata/{plugin_id}/` 디렉토리 내부의 코드 및 자원만으로 완결되어야 합니다.
- **독립 렌더링**: 코어는 각 플러그인의 비즈니스 로직에 관여하지 않습니다.

### 📊 호환성 매트릭스 (코어 ↔ 플러그인 계약)

| 코어 버전 범위 | 필수 계약 | 선택 계약 | 비고 |
| :--- | :--- | :--- | :--- |
| **1.0.0 ~ 1.0.4** | `search`, `apply` | `dashboard_widget`, `get_dashboard_data` | 폴더 기반/단일 파일 호환 지원 |
| **1.0.5 ~ 1.0.6** | `search`, `apply` | `get_context_menu_items`, `run_context_menu_action`, `update_manifest` | 도서 컨텍스트 메뉴 & 원격 자동 업데이트 지원 |
| **1.0.7+ (현재)** | `search`, `apply` | `category_tab`, `on_scan_new_books_detected`, `dispatch_webhook`, `update_manifest` | 1등 시민 메뉴, 듀얼 UI, 8종 테마 및 표준 이벤트 웹훅 병행 지원 |

---

## 2. 디렉토리 구조 규격 (Directory Structure Spec)

권장 방식은 **폴더 기반 디렉토리 구조**입니다.

```text
plugins/metadata/
  my_plugin/
    __init__.py
    my_plugin.py
    VERSION            # 필수: 자동 업데이트 지원 대상 버전 파일
    index.html         # 카테고리 레벨 풀페이지 뷰 UI 템플릿
    style.css          # 카테고리 풀페이지 뷰 CSS
    script.js          # 카테고리 풀페이지 뷰 JS
    settings.html      # 선택: 환경설정 탭 전용 커스텀 폼 UI (미작성 시 config_schema 사용)
    settings.css       # 선택: 환경설정 커스텀 폼 CSS
    settings.js        # 선택: 환경설정 커스텀 폼 JS
    requirements.txt   # 선택: 플러그인 전용 파이썬 외부 라이브러리 자동 설치 목록
```

### 🔒 런타임 보안 및 디렉토리 접근 제약 사항 (Strict Security Protections)

북오아시스 미디어 서버는 서버 및 시스템 안전성을 보장하기 위해 플러그인에 다음과 같은 **강력한 런타임 보안 제약 장치**를 적용합니다.

1. **상위 디렉토리 이탈 차단 (Path Traversal Protection)**:
   - 플러그인 UI 번들 서빙 및 정적 자원 로딩 시 `../` 또는 `..\`를 포함한 상위 디렉토리 이탈 시도가 감지되면 백엔드 `MetadataFactory`가 즉시 `SecurityError` 예외를 발생시키고 로딩을 거부합니다.
   - 모든 템플릿 자원은 해당 플러그인의 루트 디렉토리 `plugins/metadata/{plugin_id}/` 내부로 엄격히 제한됩니다.
2. **외부 심볼릭 링크 접근 차단 (Symlink Restriction)**:
   - 플러그인 폴더 외부의 시스템 중요 파일(예: `/etc/passwd`, 시스템 파일 등)을 가리키는 외부 심볼릭 링크 파일은 런타임 검증에 의해 접근이 차단됩니다.
3. **독립 패키지 격리 및 코어 최우선 보호 (Package Isolation)**:
   - `requirements.txt`로 설치되는 외부 패키지는 해당 플러그인 전용 `libs/` 폴더에 격리 설치되며, 북오아시스 코어 주요 라이브러리(`Flask`, `pypdfium2`, `Pillow` 등)의 버전을 덮어쓰거나 오염시키는 행위는 코어 보호 엔진에 의해 자동 차단됩니다.
4. **HTML5 풀 태그 지원 및 동적 데이터 XSS 방어 규칙**:
   - 카테고리 뷰 UI(`index.html`)에서는 `<canvas>`, `<svg>`, `<table>`, `<form>`, `<input>`, `<button>` 등 모든 HTML5 태그와 커스텀 CSS/JS가 100% 허용됩니다.
   - 단, 외부 3rd-party API나 사용자 입력값을 뷰포트에 동적 삽입할 경우 `textContent`나 안전한 에스케이프 기능을 사용하여 XSS 공격이 발생하지 않도록 개발자가 방어 코드를 작성해야 합니다.

### 🎨 듀얼 UI (Dual-UI) 서빙 아키텍처

BookOasis 플러그인은 화면 목적에 따라 2가지 독립된 UI 번들을 분리 서빙합니다.

1. **카테고리 레벨 풀페이지 UI (`index.html`, `style.css`, `script.js`)**:
   - 좌측 사이드바의 플러그인 카테고리 클릭 시 메인 화면 영역 전체에 마운트되는 대형 풀 뷰포트 UI입니다.
2. **환경설정 탭 커스텀 폼 UI (`settings.html`, `settings.css`, `settings.js`)**:
   - 관리자 [환경설정 ⚙️] -> [플러그인 설정] 탭 카드 내부에 표시되는 전용 커스텀 입력 폼 UI입니다.
   - `settings.html`이 존재하지 않을 경우, 플러그인 클래스의 `config_schema` 파이썬 배열을 기반으로 입체적인 설정 폼이 자동 생성됩니다.

---

## 3. 플러그인 클래스 기본 계약 (Class Contract)

모든 플러그인 클래스는 `plugins/metadata/base.py`에 정의된 `BaseMetadataProvider`를 상속받아야 합니다.
클래스 이름은 `{파일명의CamelCase}MetadataProvider` 형태를 권장합니다. (예: `GoogleMetadataProvider`)

```python
from plugins.metadata.base import BaseMetadataProvider

class MyPluginMetadataProvider(BaseMetadataProvider):
    id = "my_plugin"
    name = "나의 커스텀 플러그인"
    is_searchable = True
```

필수/권장 속성:
- `id` (str): 고유 식별자 (파일명 및 폴더명과 동일)
- `name` (str): 사용자에게 보여질 플러그인 이름
- `is_searchable` (bool): 도서 수동 매칭 검색 모달 노출 여부
- `config_schema` (list): 환경설정 폼 정의 배열
- `dashboard_widget` (dict 또는 None): 대시보드 위젯 구성 정보
- `category_tab` (dict 또는 None): 좌측 사이드바 1등 시민 카테고리 메뉴 등록 정보 (`title`, `icon`, `order`)
- `update_manifest` (dict 또는 None): 원격 자동 업데이트 선언 계약

### 🌟 카테고리 레벨 플러그인 (`category_tab`) 규격
플러그인이 대시보드 위젯 수준을 넘어 **좌측 사이드바의 1등 시민(First-class Citizen) 카테고리 메뉴**로 등록되어 풀페이지 커스텀 UI를 제공하려면 `category_tab`을 선언합니다.

```python
category_tab = {
    "title": "독서 통계 센터",
    "icon": "fa-solid fa-chart-pie",
    "order": 80
}
```

---

## 4. 설정 UI 및 `config_schema` 복합 저장 규격

웹 UI(환경설정 > 플러그인 설정)에 노출할 폼 구조를 `config_schema`에 정의합니다. 입력된 값들은 단일 JSON 객체로 직렬화되어 DB에 저장됩니다.

지원 필드 타입:
- `text`, `password`, `number`: 기본적인 입력 폼
- `checkbox`: 불리언(True/False) 스위치 폼
- `select`: 드롭다운 선택 폼 (`options` 배열 필수)

```python
config_schema = [
    {"key": "API_KEY", "label": "API 토큰", "type": "password", "required": True},
    {"key": "MAX_RETRIES", "label": "재시도 횟수", "type": "number", "default": 3},
    {"key": "ENABLE_PROXY", "label": "프록시 활성화", "type": "checkbox", "default": False},
    {"key": "REGION", "label": "서버 지역", "type": "select", "options": [
        {"value": "kr", "label": "한국 (Seoul)"},
        {"value": "us", "label": "미국 (US East)"}
    ]}
]
```

---

## 5. 대시보드 위젯 및 공통 데스크 계약 (`dashboard_widget`)

독립된 **[플러그인]** 카테고리 화면에 위젯 카드를 노출하거나 단독 탭으로 렌더링하려면 `dashboard_widget`를 선언하고 `get_dashboard_data()`를 구현하십시오.

```python
dashboard_widget = {
    "title": "신간 정보 위젯",
    "subtitle": "최신 외부 API 신간 목록",
    "provider": "MyAPI",
    "icon": "fa-solid fa-book-open",
    "limit": 10,
    "all_desk_tab": True,  # (선택) True 시 공통 데스크 카드가 아닌 단독 전체화면 탭으로 동적 렌더링됨
    "supported_types": ["general"]  # (선택) 일반/성인 보관함 노출 구별
}

def get_dashboard_data(self, db_type, limit=10):
    return {'success': True, 'items': [...]}
```

---

## 6. 도서 컨텍스트 메뉴 & 웹훅 알림 확장 계약

### 📌 컨텍스트 메뉴 확장 (`get_context_menu_items`)

도서 카드(대시보드/목록/상세 공통) 우클릭 컨텍스트 메뉴에 커스텀 메뉴 항목을 추가할 수 있습니다.

```python
def get_context_menu_items(self, db_type, context):
    return [
        {
            'id': 'open_vendor_search',
            'label': '외부 사이트에서 책 제목 검색',
            'icon': 'fa-solid fa-up-right-from-square'
        }
    ]

def run_context_menu_action(self, db_type, action_id, context):
    book_title = context.get('book_title', '')
    return {
        'success': True,
        'message': '외부 검색 페이지를 새 탭으로 엽니다.',
        'open_url': f'https://search.example.com?q={book_title}'
    }
```

### 📌 하이라이트 컨텍스트 메뉴 확장 (`get_annotation_context_menu_items`)

EPUB/TXT 뷰어에서 만든 하이라이트를 우클릭/롱프레스했을 때 뜨는 메뉴에도 동일한 방식으로 항목을 추가할 수 있습니다. `context`에는 `annotation_id`, `book_id`, `book_title`, `series_name`, `cover_image`, `format`, `chapter_idx`, `quote`, `note`, `color`가 담깁니다. `book_title`/`series_name`/`cover_image`는 코어가 `book_id`로 매번 직접 조회해서 채워주므로 플러그인에서 따로 재조회할 필요가 없습니다.

```python
def get_annotation_context_menu_items(self, db_type, context):
    return [
        {
            'id': 'export_to_notes_app',
            'label': '메모 앱으로 내보내기',
            'icon': 'fa-solid fa-file-export'
        }
    ]

def run_annotation_context_menu_action(self, db_type, action_id, context):
    quote = context.get('quote', '')
    return {
        'success': True,
        'message': '전송했습니다.',
        'open_url': f'obsidian://new?vault=MyVault&content={quote}',
        'marker': '*'  # 하이라이트 뒤에 위첨자로 표시 - 코어 DB 밖에 저장해도 "저장됨"이 보이게
    }
```

메모를 코어 `note` 컬럼이 아니라 플러그인 자체 저장소(JSONL 등)에 두면 코어는 무엇이 저장됐는지 전혀 모르므로, `marker` 응답 필드로 "이 하이라이트에 뭔가 달려있다"는 표시만 위임할 수 있습니다. 사용자 입력이 필요한 액션(예: 메모 직접 작성)은 `prompt` 응답 필드로 입력 모달을 띄우고 같은 action_id로 재호출받는 왕복 패턴을 지원합니다 — 전체 예제는 [sample_plugins/metadata/highlight_notes_sample/highlight_notes_sample.py](../../sample_plugins/metadata/highlight_notes_sample/highlight_notes_sample.py) 참고.

자세한 계약/필드 설명은 [docs/guide_plugins.md의 7장](../../docs/guide_plugins.md)을 참고하세요. 하이라이트 CRUD REST API(`/api/v1/books/<book_id>/annotations`)는 세션 인증만 있으면 플러그인 웹뷰에서 `fetch()`로 직접 호출할 수 있습니다.

### 🔔 신규 도서 감지 웹훅 이벤트 (`on_scan_new_books_detected`)

스캐너가 라이브러리 스캔을 완료하고 신규 도서를 감지했을 때 코어로부터 직접 이벤트를 전달받아 Discord, Slack, Telegram 등으로 웹훅을 전송할 수 있습니다.

---

## 7. 🎨 Dashboard Theme System Integration & UI Inheritance (대시보드 테마 시스템 연동 및 UI 상속 가이드)

BookOasis supports 8 dashboard custom themes (`purple`, `dark`, `light`, `sepia`, `blue`, `aquamarine`, `ironman`, `epaper`).
BookOasis는 8종의 대시보드 커스텀 테마를 지원합니다. 플러그인 UI가 사용자의 대시보드 테마 변경에 100% 실시간으로 연동되어 일관된 디자인을 유지하도록 개발 시 아래 전역 CSS 변수를 사용하세요.

### 🎨 Global CSS Design Tokens (전역 CSS 디자인 토큰 변수)

All plugin UI/HTML/CSS templates should use the global CSS variables below instead of hardcoded colors (e.g. `#ffffff`, `#1e293b`).
모든 플러그인 UI/HTML/CSS 작성 시 하드코딩된 색상 대신 아래 전역 변수를 사용하면 테마 변경 시 자동으로 전용 색조로 전환됩니다.

| CSS 변수 (Custom Property) | Description (설명 및 용도) | Usage Example (추천 사용 예시) |
| :--- | :--- | :--- |
| `var(--app-bg-main)` | Main background color / 메인 배경색 | 메인 컨테이너 배경 |
| `var(--app-bg-sidebar)` | Sidebar & header background / 사이드바·상단바 배경 | 헤더, 사이드바 영역 |
| `var(--app-bg-card)` | Card & container box background / 카드·박스 배경 | 위젯 카드, 테이블, 폼 박스 |
| `var(--app-bg-card-hover)` | Card hover background / 카드 호버 배경 | 마우스 오버 반응 효과 |
| `var(--app-text-primary)` | Primary text color / 기본 텍스트 색상 | 주요 제목, 본문 글씨 |
| `var(--app-text-muted)` | Muted text color / 보조 텍스트 색상 | 설명문, 타임스탬프, 캡션 |
| `var(--app-text-secondary)` | Secondary text color / 강조 보조 텍스트 | 서브 타이틀, 하이라이트 글씨 |
| `var(--app-accent)` | Theme accent color / 테마 메인 강조 색상 | 주요 버튼, 활성 탭, 뱃지 |
| `var(--app-accent-hover)` | Accent hover color / 강조 색상 호버 | 버튼 마우스 오버 시 |
| `var(--app-border)` | Primary border color / 기본 테두리 색상 | 카드/입력창 테두리 |
| `var(--app-border-light)` | Light border color / 은은한 구분선 색상 | 항목 간 구분선(`border-bottom`) |
| `var(--app-input-bg)` | Input form background / 입력창 배경색 | `input`, `select`, `textarea` |

---

### 💻 Theme Integration Example Code (테마 연동 실전 예시 코드)

#### 1) HTML (`index.html`) & CSS (`style.css`) 예시

```html
<!-- plugins/metadata/my_plugin/index.html -->
<div class="my-plugin-card">
    <div class="my-plugin-header">
        <h4 class="my-plugin-title">플러그인 대시보드 위젯</h4>
        <span class="my-plugin-badge">ACTIVE</span>
    </div>
    <p class="my-plugin-desc">현재 선택된 대시보드 테마와 100% 동기화되어 디자인이 변경됩니다.</p>
    <button class="my-plugin-btn">실행하기</button>
</div>
```

```css
/* plugins/metadata/my_plugin/style.css */
.my-plugin-card {
    background: var(--app-bg-card);
    border: 1px solid var(--app-border);
    border-radius: 8px;
    padding: 1.25rem;
    box-shadow: var(--app-shadow, 0 4px 12px rgba(0,0,0,0.1));
    transition: background-color 0.3s ease, border-color 0.3s ease;
}

.my-plugin-card:hover {
    background: var(--app-bg-card-hover);
}

.my-plugin-title {
    color: var(--app-text-primary);
    font-size: 1.1rem;
    margin: 0;
}

.my-plugin-desc {
    color: var(--app-text-muted);
    font-size: 0.88rem;
}

.my-plugin-btn {
    background: var(--app-accent);
    color: #ffffff;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
}

.my-plugin-btn:hover {
    background: var(--app-accent-hover);
}
```

#### 2) JavaScript (`script.js`) & Dynamic Theme Event Listener (실시간 테마 감지)

```javascript
// plugins/metadata/my_plugin/script.js

function getCurrentTheme() {
    return document.documentElement.getAttribute('data-app-theme') || 'purple';
}

const themeObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'data-app-theme') {
            const newTheme = getCurrentTheme();
            console.log(`[MyPlugin] 테마 변경 감지됨: ${newTheme}`);
            onThemeChanged(newTheme);
        }
    });
});

themeObserver.observe(document.documentElement, { attributes: true });

function onThemeChanged(themeName) {
    // 차트 또는 커스텀 JS 그래픽 색상 재설정 로직
}
```

#### 3) External iframe Plugin Theme Synchronization (iframe 기반 독립 플러그인 테마 수신)

```javascript
// iframe 내부 플러그인 JS 코드 예시
window.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'BOOKOASIS_THEME_CHANGE') {
        const currentTheme = event.data.theme;
        document.documentElement.setAttribute('data-app-theme', currentTheme);
    }
});
```

---

## 8. 구현 예시 코드 & DB 게이트웨이 활용

### 💾 안전한 DB 액세스 (`self.get_db_gateway()`)

플러그인 내부에서 `import database`를 직접 호출하는 대신, Base Class가 제공하는 게이트웨이를 사용하십시오.

```python
def _get_total_books(self, db_type):
    gateway = self.get_db_gateway(db_type)
    row = gateway.fetch_one("SELECT COUNT(*) AS cnt FROM books WHERE COALESCE(is_deleted, 0) = 0")
    return int((row["cnt"] if row else 0) or 0)
```

---

## 9. 💡 Tip: iframe 외부 연동 시 보안 제약 사항 안내

독립된 플러그인 화면에서 `<iframe>`을 사용해 외부 웹 서비스를 끌어오고자 할 때는 브라우저 보안 제약에 유의해야 합니다.

1. **X-Frame-Options / CSP 차단**:
   - `X-Frame-Options: SAMEORIGIN` 또는 `Content-Security-Policy` 헤더를 통해 프레임 삽입을 차단하는 메이저 웹 사이트(예: Google, Naver 등)는 iframe으로 직접 로드가 불가능합니다.
   - **해결 방안**: 직접 Proxy API를 구축할 필요 없이, 아래 §10에서 소개하는 코어 제공 웹뷰 API(`window.BookOasisPlugin.openWebview`)를 사용하십시오. 이미 프록시+헤더 제거가 구현되어 있습니다.
2. **Mixed Content 차단**:
   - BookOasis 웹 서비스가 SSL(HTTPS) 환경에서 제공되는 경우, iframe 내부의 URL 역시 반드시 `https://` 보안 통신 주소여야 합니다. (`http://` 주소는 브라우저에 의해 자동 차단됨)

---

## 10. 🌐 외부 도메인 웹뷰 & 다운로드 API

플러그인이 외부 사이트를 앱 내에서 보여주거나, 외부 URL의 파일을 라이브러리로 다운로드해야 할 때 사용하는 코어 제공 API입니다.

**중요 — 책임 소재**: BookOasis는 어떤 외부 도메인도 기본 제공하거나 추천하지 않습니다. 이 API는 **각 사용자가 [설정 > 외부 도메인] 탭에서 직접 등록한 화이트리스트**에 있는 도메인에 대해서만 동작합니다. 플러그인이 임의로 화이트리스트를 추가/우회할 수 없으며, 사용자가 어떤 도메인을 등록하고 무엇을 하는지는 전적으로 사용자 본인의 책임입니다.

### `window.BookOasisPlugin.openWebview(url)`
지정한 URL을 서버 프록시를 통해 가져와서 앱 내 모달(iframe)로 표시합니다.

```js
window.BookOasisPlugin.openWebview('https://example.com/some-page');
```

- `url`의 호스트가 사용자의 화이트리스트에 없으면 안내 토스트만 뜨고 아무 것도 열리지 않습니다. **정확 매칭**이라 `example.com`만 등록해도 `www.example.com`은 별개 호스트로 취급되어 거부됩니다 — 서브도메인까지 포함하려면 `*.example.com` 형태(와일드카드)로 등록해야 합니다.
- 서버가 SSRF 방어(사설/루프백 IP 차단, 리다이렉트 재검증, 응답 크기 제한 15MB)를 수행하므로, 화이트리스트에 등록되어 있어도 일부 요청은 거부될 수 있습니다.
- 응답이 HTML이면 `<base href="원본사이트">` 태그를 자동 주입해 상대경로 이미지/CSS/JS/링크가 프록시가 아닌 원본 사이트 기준으로 풀리도록 합니다. 다만 완전한 자산 재작성기는 아니라서 인라인 `style="background:url(...)"` 같은 경우까지는 처리하지 못하며, 무거운 SPA/리치 웹사이트는 여전히 깨질 수 있습니다 — 단순~중간 복잡도의 서버 렌더링 페이지에 적합합니다.

### `window.BookOasisPlugin.downloadToLibrary(url, { libraryId, dbType })`
지정한 URL의 파일을 다운로드해서 선택한 라이브러리 물리 경로에 저장하고, 스캐너로 즉시 임포트합니다.

```js
window.BookOasisPlugin.downloadToLibrary('https://example.com/book.epub', {
  libraryId: 12,
  dbType: 'general' // 생략 시 'general'
});
```

- 화이트리스트 검증 + SSRF 방어(응답 크기 제한 500MB)를 거칩니다.
- 호출한 사용자가 대상 라이브러리에 접근 권한이 없으면 실패합니다.
- 지원 확장자(`.zip .cbz .epub .pdf .txt`)가 아니면 파일은 저장되지만 도서로 임포트되지는 않습니다(`imported_as_book: false`).
- 반환값(Promise)은 `{ success, filename, imported_as_book, warning?, scan_error? }` 형태입니다.

플러그인 Python 백엔드에서 직접 다운로드/프록시 로직을 새로 구현할 필요 없이 위 두 API를 재사용하십시오 — 화이트리스트 관리, SSRF 방어, 스캔 트리거가 이미 구현되어 있습니다.

### `window.BookOasisPlugin.getSession()`
`category_tab` 플러그인은 iframe이 아니라 호스트와 **같은 DOM/JS 컨텍스트**에서 실행되므로(사이드바/설정 화면과 동일한 페이지), 이 함수는 서버 왕복 없이 현재 세션 정보를 동기적으로 즉시 반환합니다.

```js
const session = window.BookOasisPlugin.getSession();
// { libraryType: 'general' | 'adult' | 'audiobook' | 'video', categoryId, username, role }
```

- `libraryType`: 상단 헤더의 일반/성인/오디오북/영상강좌 탭 중 현재 활성 세션.
- `categoryId`: 현재 선택된 사이드바 카테고리 id (예: `'home'`, `'history'`, 플러그인 자신의 카테고리 id 등).
- `username` / `role`: 로그인한 사용자 정보. 비로그인 상태이거나 아직 로드 전이면 `null`일 수 있습니다.

세션이 바뀔 때마다 실시간으로 반응하려면 `bookoasis:session-change` 커스텀 이벤트를 구독하십시오 (앱 최초 로드 시 1회 + 세션 전환마다 항상 발생):

```js
window.addEventListener('bookoasis:session-change', (event) => {
  console.log('현재 세션:', event.detail.libraryType);
});
```

### 참조 구현: `gutenberg_browser` 샘플 플러그인

- 경로: `plugins/metadata/gutenberg_browser/`
- `category_tab`으로 사이드바 1등 시민 메뉴 등록 + `index.html`/`script.js`에서 `openWebview()`(Project Gutenberg 웹사이트 열기)와 `downloadToLibrary()`(입력한 URL을 선택한 라이브러리로 다운로드) 두 API를 모두 시연합니다.
- 라이브러리 목록은 `GET /api/media/libraries?type=general`로 조회해 `<select>`를 채우는 방식을 참고하십시오.
