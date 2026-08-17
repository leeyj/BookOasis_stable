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
  my_plugin/
    __init__.py
    my_plugin.py
    VERSION            # 필수: 자동 업데이트 지원 대상 버전 파일
    index.html         # 카테고리 풀페이지 뷰 UI 템플릿
    style.css          # 카테고리 풀페이지 뷰 CSS
    script.js          # 카테고리 풀페이지 뷰 JS
    settings.html      # 선택: 환경설정 탭 전용 커스텀 폼 UI (미작성 시 config_schema 사용)
    settings.css       # 선택: 환경설정 커스텀 폼 CSS
    settings.js        # 선택: 환경설정 커스텀 폼 JS
    requirements.txt   # 선택: 플러그인 전용 파이썬 외부 라이브러리 자동 설치 목록
```

### 🔒 보안 및 디렉토리 접근 제약 사항 (Strict Security Protections)

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

### 🎨 대시보드 테마 시스템 연동 및 UI 상속 가이드 (Dashboard Theme Integration & UI Inheritance)

BookOasis supports 8 dashboard custom themes (`purple`, `dark`, `light`, `sepia`, `blue`, `aquamarine`, `ironman`, `epaper`).
BookOasis는 8종의 대시보드 커스텀 테마를 지원합니다. 플러그인 UI가 사용자의 대시보드 테마 변경에 100% 실시간으로 연동되어 일관된 디자인을 유지하도록 아래 전역 CSS 변수를 사용하세요.

#### 🎨 Global CSS Design Tokens (전역 CSS 디자인 토큰 변수)

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

#### 💻 Theme Integration Example Code (테마 연동 실전 예시 코드)

##### 1) HTML (`index.html`) & CSS (`style.css`) Sample

```html
<!-- plugins/metadata/my_plugin/index.html -->
<div class="my-plugin-card">
    <div class="my-plugin-header">
        <h4 class="my-plugin-title">플러그인 대시보드 위젯 (Plugin Dashboard Widget)</h4>
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

##### 2) JavaScript (`script.js`) & Dynamic Theme Event Listener

```javascript
// plugins/metadata/my_plugin/script.js

// Get active dashboard theme identifier / 현재 적용된 대시보드 테마 식별자 가져오기
function getCurrentTheme() {
    return document.documentElement.getAttribute('data-app-theme') || 'purple';
}

// Observe dynamic theme attribute changes / 테마 변경 동적 감지 (HTML data-app-theme 모니터링)
const themeObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'data-app-theme') {
            const newTheme = getCurrentTheme();
            console.log(`[MyPlugin] Theme changed: ${newTheme}`);
            onThemeChanged(newTheme);
        }
    });
});

themeObserver.observe(document.documentElement, { attributes: true });

function onThemeChanged(themeName) {
    // Re-render chart or canvas elements if needed / 필요 시 차트나 캔버스 재그리기
}
```

##### 3) External iframe Plugin Theme Synchronization (iframe 독립 플러그인 테마 수신)

```javascript
// Inside iframe plugin JS code / iframe 내부 플러그인 수신 코드
window.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'BOOKOASIS_THEME_CHANGE') {
        const currentTheme = event.data.theme; // e.g. 'ironman', 'aquamarine'
        document.documentElement.setAttribute('data-app-theme', currentTheme);
    }
});
```

---

## 3. 플러그인 클래스 기본 계약

모든 플러그인 클래스는 [plugins/metadata/base.py](../plugins/metadata/base.py)를 상속해야 합니다.

필수/권장 필드:

- `id` (str): 고유 식별자
- `name` (str): UI 표시명
- `is_searchable` (bool): 수동 메타데이터 검색 모달 노출 여부
- `config_schema` (list): 설정 폼 스키마 (기본 자동 생성 폼용)
- `dashboard_widget` (dict 또는 None): 대시보드 위젯 메타 (공통 데스크 카드 또는 단독 탭 뷰 구성 정보)
- `category_tab` (dict 또는 None): 카테고리 레벨 플러그인 매니페스트 (사이드바 카테고리 1등 시민 메뉴 등록 정보: `title`, `icon`, `order`, `sessions`)
- `update_manifest` (dict 또는 None): 플러그인 내부 업데이트 선언 계약

### 카테고리 레벨 플러그인 (Category-Level Plugins) 규격
플러그인이 대시보드 위젯 수준을 넘어 **좌측 사이드바의 1등 시민(First-class Citizen) 카테고리 메뉴**로 등록되어 풀페이지 커스텀 UI를 제공하려면 `category_tab`을 선언합니다.

```python
class MyCategoryPlugin(BaseMetadataProvider):
    id = "my_category_plugin"
    name = "나만의 커스텀 서재"
    is_searchable = False

    category_tab = {
        "title": "나만의 커스텀 서재",
        "icon": "fa-solid fa-chart-line",
        "order": 80,
        "sessions": "all"  # 선택 사항. 아래 "노출 세션 지정" 참고
    }
```

#### 노출 세션 지정 (`sessions`)
`category_tab.sessions`로 이 플러그인이 어느 세션(일반 도서/성인 서재/오디오북/영상 강좌)의 사이드바에 노출될지 선언할 수 있습니다.

- 생략 시 기본값은 `일반 도서(general)` 단일 세션입니다(하위 호환).
- `"all"`: 4개 세션(general/adult/audiobook/video) 전체에 노출.
- `["adult"]`처럼 리스트로 특정 세션만 지정 가능. 예를 들어 성인용 콘텐츠를 다루는 플러그인은 `sessions: ["adult"]`로 선언하면 일반 도서 사이드바에는 나타나지 않고 성인 서재 세션에만 노출됩니다.
- 계정별 노출 여부(권한 on/off)는 여전히 설정 → 권한 관리의 '일반 도서' 탭 매트릭스에서 관리합니다. `sessions`는 "어느 세션에 뜰지"를, 권한 매트릭스는 "어느 사용자에게 뜰지"를 결정하는 별개의 축입니다.

#### UI 템플릿 태그 규격 (HTML5 풀 지원)
카테고리 레벨 플러그인의 `index.html`, `style.css`, `script.js` 템플릿 화면에서는 **`<canvas>`, `<svg>`, `<table>`, `<form>`, `<input>`, `<button>` 등 모든 HTML5 태그와 CSS, JS가 100% 제약 없이 자유롭게 허용**됩니다.

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

- [sample_plugins/metadata/naver_book/naver_book.py](../sample_plugins/metadata/naver_book/naver_book.py)

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
- `db_type`은 `general`/`adult`뿐 아니라 `audiobook`도 포함됩니다. 오디오북 스캐너(`services/audiobook_scanner.py`)는 별도 파이프라인이지만 동일한 `on_scan_new_books_detected` 훅 경로를 재사용하도록 연결되어 있어, 별도 처리 없이 같은 플러그인 훅으로 오디오북 신간도 감지됩니다. 자세한 내부 동작은 [spec_scanner_logic.md](./spec_scanner_logic.md#3-오디오북-스캐너-완전히-분리된-파이프라인)를 참고하세요.

### 비공개(private) 플러그인 선택적 활성화 (ADD_PLUGIN, 베타 테스트 단계)

커뮤니티 개발자와 합의된 규약입니다. `plugins/metadata/` 디렉토리에 코드가 존재하면 누구나 그 플러그인을 볼 수 있기 때문에, 특정 운영자에게만 배포되는 비공개 플러그인(예: 사내/유료 플러그인)은 **운영자가 명시적으로 opt-in하지 않는 한 자기 자신을 비활성 상태로 유지**해야 합니다.

> ⚠️ 베타 테스트 단계이므로 현재는 고정된 단일 plugin_id **`--------`** 하나만 지원합니다. 다른 plugin_id를 등록해도 무시되며, 다중 plugin_id 허용목록 방식은 아직 지원하지 않습니다(추후 필요 시 확장 예정).

- 운영자는 `.env` 또는 `docker-compose.override.yml`의 `environment:` 항목에 `ADD_PLUGIN=security-bookoasis-plugin`을 정확히 설정합니다.
- (선택) 환경설정 화면 없이도 DB `settings` 테이블에 `ADD_PLUGIN` 키를 직접 저장하면 이 값이 `.env` 값보다 우선 적용됩니다.
- 플러그인 코드는 자신의 활성화 여부를 결정하는 시점(예: `on_scan_new_books_detected`, `get_dashboard_data`, `search` 등 훅 진입부)에 아래 API를 호출해 `ADD_PLUGIN` 값이 자신의 고정 plugin_id와 정확히 일치하는지 확인합니다. 일치하지 않으면 아무 동작도 하지 않고 조용히 빈 결과/`success: False`를 반환해야 합니다.

```
GET /api/media/plugins/add-plugin-check?plugin_id=123412341234123412341234
```

응답 예시:

```json
{"success": true, "plugin_id": "security-bookoasis-plugin", "enabled": true}
```

- 이 API는 로그인 세션 없이도 호출 가능합니다(다른 플러그인 부트스트랩용 API와 동일한 공개 조회 성격).
- 조회한 `plugin_id`가 고정값과 일치하는지 여부만 반환하며, 서버에 설정된 `ADD_PLUGIN` 값 자체는 절대 노출하지 않습니다.
- 이 게이트는 기존 `PLUGIN_ENABLED_{id}` DB 토글(관리자 UI에서 켜고 끄는 값)과는 별개입니다. `ADD_PLUGIN`은 "존재 자체를 드러낼지"를 결정하고, `PLUGIN_ENABLED_{id}`는 이미 노출이 허용된 플러그인의 통상적인 on/off를 담당합니다.

**샘플 코드**: [plugins/metadata/__template_add_plugin_gate.py](../plugins/metadata/__template_add_plugin_gate.py)를 그대로 복사해 시작하세요. 파일명이 `__`로 시작하므로 플러그인 자동 탐색 대상에서 제외되어(다른 템플릿인 `__template_dashboard_plugin.py`와 동일한 관례) 그대로 두어도 실제 플러그인으로 로드되지 않습니다. `_is_add_plugin_enabled()`가 위 API를 호출해 결과를 60초간 캐시하고, 네트워크 오류 시에도 항상 "비활성화"로 안전하게 처리(fail-closed)하는 예시이며, `search`/`apply`뿐 아니라 `on_scan_new_books_detected` 같은 훅에도 동일한 패턴을 적용하는 법을 보여줍니다.

### 신규도서 웹훅 알림 예제 플러그인

- 경로: `sample_plugins/metadata/webhook_new_books_notify/webhook_new_books_notify.py`
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

예시 플러그인: `sample_plugins/metadata/stats_dashboard/stats_dashboard.py`

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

## 10. 🌐 외부 도메인 웹뷰 & 다운로드 API

플러그인이 외부 사이트를 앱 내에서 보여주거나, 외부 URL의 파일을 라이브러리로 다운로드해야 할 때 쓰는 코어 제공 API입니다.

**책임 소재**: BookOasis는 어떤 외부 도메인도 기본 제공/추천하지 않습니다. 이 API는 **각 사용자가 [설정 > 외부 도메인] 탭에서 직접 등록한 화이트리스트**에 있는 도메인에 대해서만 동작합니다. 플러그인이 임의로 화이트리스트를 추가/우회할 수 없으며, 어떤 도메인을 등록하고 무엇을 하는지는 전적으로 사용자 본인의 책임입니다.

### `window.BookOasisPlugin.openWebview(url)`

서버 프록시를 통해 URL을 가져와 앱 내 모달(iframe)로 표시합니다.

```js
window.BookOasisPlugin.openWebview('https://example.com/some-page');
```

- 호스트가 사용자의 화이트리스트에 없으면 안내 토스트만 뜨고 아무 것도 열리지 않습니다. **정확 매칭**이라 `example.com`만 등록해도 `www.example.com`은 별개 호스트로 취급되어 거부됩니다 — 서브도메인까지 포함하려면 `*.example.com` 형태(와일드카드)로 등록해야 합니다.
- 서버가 SSRF 방어(사설/루프백 IP 차단, 리다이렉트 재검증, 응답 크기 제한 15MB)를 수행하므로 화이트리스트에 있어도 일부 요청은 거부될 수 있습니다.
- 응답이 HTML이면 `<base href="원본사이트">`를 자동 주입해 상대경로 이미지/CSS/JS/링크가 프록시가 아닌 원본 사이트 기준으로 풀리도록 합니다. 완전한 자산 재작성기는 아니라서(예: 인라인 `style="background:url(...)"`) 무거운 SPA는 여전히 깨질 수 있습니다.

### `window.BookOasisPlugin.downloadToLibrary(url, { libraryId, dbType })`

URL의 파일을 다운로드해 선택한 라이브러리 물리 경로에 저장하고, 스캐너로 즉시 임포트합니다.

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

플러그인 Python 백엔드에서 직접 다운로드/프록시 로직을 새로 구현할 필요 없이 위 두 API를 재사용하십시오. 실제 사용 예시는 아래 참조 구현을 확인하십시오.

### 참조 구현: `gutenberg_browser` 샘플 플러그인

- 경로: `sample_plugins/metadata/gutenberg_browser/`
- `category_tab`으로 사이드바 1등 시민 메뉴 등록 + `index.html`/`script.js`에서 `openWebview()`(Project Gutenberg 웹사이트 열기)와 `downloadToLibrary()`(입력한 URL을 선택한 라이브러리로 다운로드) 두 API를 모두 시연합니다.
- 라이브러리 목록은 `GET /api/media/libraries?type=general`로 조회해 `<select>`를 채우는 방식을 참고하십시오.

---

## 💡 Tip: iframe 외부 연동 시 보안 제약 사항 안내
독립된 플러그인 화면에서 `<iframe>`을 사용해 외부 웹 서비스를 끌어오고자 할 때는 브라우저 보안 제약에 유의해야 합니다.

1. **X-Frame-Options / CSP 차단**:
   - `X-Frame-Options: SAMEORIGIN` 또는 `Content-Security-Policy` 헤더를 통해 자신들의 사이트가 타사 사이트에 프레임 형태로 삽입되는 것을 차단하는 사이트(예: Google, Naver 등)는 iframe으로 직접 로딩이 불가능합니다.
   - **해결 방안**: 직접 Proxy API를 구축할 필요 없이 위 §10의 `window.BookOasisPlugin.openWebview()`를 사용하십시오 — 프록시와 헤더 제거가 이미 구현되어 있습니다.
2. **Mixed Content 차단**:
   - BookOasis 웹 서비스가 SSL(HTTPS) 환경에서 제공되는 경우, iframe 내에 호출되는 주소 역시 반드시 `https://` 보안 통신 주소여야 합니다. `http://`로 시작하는 일반 주소는 브라우저 보안 규격(Mixed Content)에 의해 자동으로 로드가 완전 차단됩니다.
