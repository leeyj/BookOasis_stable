# 🧩 Metadata Provider Plugin Guide (메타데이터 프로바이더 플러그인 개발 가이드)

이 문서는 BookOasis 미디어 서버에서 코어 소스코드 수정 없이 메타데이터 프로바이더, 대시보드 위젯, 카테고리 레벨 커스텀 뷰포트, 그리고 이벤트 웹훅 플러그인을 추가하는 **최신 1.0.7+ 규격**을 설명합니다.

> 💡 **참고**: 스캐너 로컬 파서 개발은 [스캐너 파서 개발 가이드](../../docs/guide_scanner_parser.md)를 참조하십시오.

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
   - `requirements.txt`로 설치되는 외부 패키지는 해당 플러그인 전용 `libs/` 폴더에 격리 설치되며, 북오아시스 코어 주요 라이브러리(`Flask`, `PyMuPDF`, `Pillow` 등)의 버전을 덮어쓰거나 오염시키는 행위는 코어 보호 엔진에 의해 자동 차단됩니다.
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
   - **해결 방안**: 플러그인 파이썬 백엔드(Python)에서 `requests`로 웹 콘텐츠를 가져온 뒤 보안 헤더를 제거하여 반환하는 Proxy API를 구축하거나, `target="_blank"` 속성을 사용하여 새 창/새 탭으로 링크아웃 처리하십시오.
2. **Mixed Content 차단**:
   - BookOasis 웹 서비스가 SSL(HTTPS) 환경에서 제공되는 경우, iframe 내부의 URL 역시 반드시 `https://` 보안 통신 주소여야 합니다. (`http://` 주소는 브라우저에 의해 자동 차단됨)
