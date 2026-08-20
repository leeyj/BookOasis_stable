# 🧩 Plugin Development Guide (New Standard)

This document describes the current plugin standard for BookOasis metadata/dashboard plugins.

> Scope: external provider plugins under `plugins/metadata/`.
> For scanner parser modules, use [guide_scanner_parser.md](./guide_scanner_parser.md).

---

## 1. Core Principle

- The core must not know plugin-specific names, routes, or internal helper methods.
- The core only relies on shared contracts.
- Plugin extension should be completed inside `plugins/metadata/` without core code forks.

### Compatibility Matrix (Core ↔ Plugin Contract)

| Core Version Range | Required Contract | Optional Contract | Notes |
| :--- | :--- | :--- | :--- |
| 1.0.0 ~ 1.0.4 | `search`, `apply` | `dashboard_widget`, `get_dashboard_data` | Both folder-based and single-file plugins supported |
| 1.0.5 ~ 1.0.6 | `search`, `apply` | `get_context_menu_items`, `run_context_menu_action`, `update_manifest` | Context menu and sample update support |
| 1.0.7+ (current) | `search`, `apply` | `on_scan_new_books_detected`, `dispatch_webhook`, `update_manifest` | Standard event webhooks (`book.new/read/finish`) recommended |

Compatibility rules:

- Core guarantees only the **required contract**.
- Optional hooks may be unavailable in older cores; implement plugin-side feature detection/fallbacks.

---

## 2. Directory Structure

Folder-based layout is recommended.

```text
plugins/metadata/
  my_plugin/
    __init__.py
    my_plugin.py
    VERSION            # Required: version file for auto-update
    index.html         # Category Full-Page View UI template
    style.css          # Category Full-Page View CSS
    script.js          # Category Full-Page View JS
    settings.html      # Optional: Custom Settings Form UI (defaults to config_schema)
    settings.css       # Optional: Custom Settings Form CSS
    settings.js        # Optional: Custom Settings Form JS
    requirements.txt   # Optional: 3rd-party python dependencies
```

### 🔒 Security & Directory Constraints (Strict Protections)

BookOasis media server enforces strict **runtime security constraints**:

1. **Path Traversal Protection (`../` Blocked)**:
   - When serving UI templates or static assets, any attempt to break out of the directory using `../` or `..\` is detected and blocked by `MetadataFactory`, raising a `SecurityError`.
   - Template resources are strictly isolated within `plugins/metadata/{plugin_id}/`.
2. **Symlink Restrictions**:
   - Symlinks pointing to paths outside the plugin directory (such as `/etc/passwd` or system files) are forbidden and rejected.
3. **Package & Core Protection**:
   - Packages specified in `requirements.txt` are installed into an isolated `libs/` subfolder. Attempts to overwrite core framework packages (`Flask`, `PyMuPDF`, `Pillow`, etc.) are automatically blocked.
4. **Unrestricted HTML5 Tags & XSS Mitigation Rules**:
   - Full HTML5 tags (`<canvas>`, `<svg>`, `<table>`, `<form>`, `<input>`, `<button>`) and custom CSS/JS are allowed in `index.html`.
   - Developers must sanitize external 3rd-party API responses before rendering to prevent XSS.

### 🎨 Dual-UI Serving Architecture

BookOasis plugins support dual UI bundles tailored to specific views:

1. **Category-Level Full-Page View UI (`index.html`, `style.css`, `script.js`)**:
   - Rendered in full-page viewport when clicking the plugin's category item in the left sidebar.
2. **Admin Settings Form UI (`settings.html`, `settings.css`, `settings.js`)**:
   - Rendered inside the plugin configuration card under **[Settings ⚙️] -> [Plugin Settings]**.
   - If `settings.html` is omitted, BookOasis automatically generates standard form inputs from the plugin's `config_schema` array.

---

## 3. Provider Contract

All providers must inherit [plugins/metadata/base.py](../plugins/metadata/base.py).

Recommended class attributes:

- `id` (str): plugin identifier
- `name` (str): display name
- `is_searchable` (bool): show in manual metadata search modal
- `config_schema` (list): settings form schema (used for auto-generated form)
- `dashboard_widget` (dict or None): dashboard widget metadata
- `category_tab` (dict or None): category-level plugin manifest (`title`, `icon`, `order`, `sessions`)
- `update_manifest` (dict or None): plugin-owned update declaration contract

### Category-Level Plugins Specification
To promote a plugin beyond a dashboard widget into a **First-Class Citizen Category Menu in the Left Sidebar** with full-page custom UI:

```python
class MyCategoryPlugin(BaseMetadataProvider):
    id = "my_category_plugin"
    name = "My Custom Library"
    is_searchable = False

    category_tab = {
        "title": "My Custom Library",
        "icon": "fa-solid fa-chart-line",
        "order": 80,
        "sessions": "all"  # optional, see "Scoping to sessions" below
    }
```

#### Scoping to sessions (`sessions`)
`category_tab.sessions` declares which session(s) — general/adult/audiobook/video — this plugin's sidebar tab appears under.

- Omitted: defaults to `general` only (backward-compatible with plugins written before this field existed).
- `"all"`: appears in all 4 sessions.
- A list like `["adult"]` restricts it to specific sessions — e.g. an adult-content plugin declaring `sessions: ["adult"]` will never appear under the general-books sidebar, only under the adult session.
- Per-account visibility (on/off per user) is still managed separately, from the 'General' tab of the admin permission matrix. `sessions` controls *which session it can appear in*; the permission matrix controls *which users see it*.

#### UI Template Tag Specification (Full HTML5 Support)
Category-level plugin UI templates (`index.html`, `style.css`, `script.js`) enjoy **100% unrestricted HTML5 tags (`<canvas>`, `<svg>`, `<table>`, `<form>`, `<input>`, `<button>`) and custom CSS/JS execution**.

Required methods:

- `search(self, db_type, query)`
- `apply(self, db_type, book_id, item_data)`

Dashboard method (for widget plugins):

- `get_dashboard_data(self, db_type, limit=10)`

Return shape:

- Success: `{'success': True, 'items': [...]}`
- Failure: `{'success': False, 'error': '...'}`

### Plugin-Owned Update Contract (`update_manifest`)

Update button visibility and execution rules are not core hardcoding anymore. They are driven by each plugin's own `update_manifest` declaration.

Example (same pattern as `stats_dashboard`):

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

Field notes:

- `enabled`: whether update support is enabled
- `provider`: currently only `github-raw` is supported
- `raw_base_url`: source path for plugin files
- `files`: files to replace during update
- `version_file`: version source file
- `version_key`: JSON key for version parsing (recommended: `plugin version`)
- `show_sample_update_button`: whether to show sample update button in settings

Execution policy:

- Update is allowed only when `current version < GitHub version`
- 404 on `raw_base_url/files` is expected before push; retry after publishing files

---

## 4. Settings Schema & UI Assets

Plugin config values are serialized into JSON and stored in:

- `settings.key = PLUGIN_CONFIG_{id}`

Supported field types:

- `text`, `password`, `number`
- `checkbox`
- `select` (requires `options`)

Example:

```python
config_schema = [
    {"key": "API_KEY", "label": "API Key", "type": "password", "required": True},
    {"key": "ENABLE_PROXY", "label": "Enable Proxy", "type": "checkbox", "default": False},
    {"key": "REGION", "label": "Region", "type": "select", "options": [
        {"value": "kr", "label": "Korea"},
        {"value": "us", "label": "United States"}
    ]}
]
```

Optional custom settings UI files:

- `index.html`
- `style.css`
- `script.js`

If present, they are automatically loaded in Settings > Plugin Settings.

---

## 5. Dashboard Widget & Exclusive Tab Contract

To render a card inside the dedicated **[Plugins]** category screen, or to display it as an exclusive full-screen tab, define `dashboard_widget` and implement `get_dashboard_data()`.

Example:

```python
dashboard_widget = {
    'title': 'New Releases',
    'subtitle': 'External provider feed',
    'provider': 'Example API',
    'icon': 'fa-solid fa-book-open',
    'limit': 10,
    'all_desk_tab': True,  # (Optional) If True, rendered as an exclusive full-width tab instead of a card (Default: False)
    'supported_types': ['general'],  # (Optional) Allowed library types (e.g. ['general', 'adult']). Omit to display on both.
}

def get_dashboard_data(self, db_type, limit=10):
    return {'success': True, 'items': []}
```

### Layout & Sorting (Sortable.js)
- Widgets with `'all_desk_tab': False` (or omitted) are grouped under the **[Common Desk]** tab in a responsive card grid.
- Users can drag and drop these widget cards to arrange their layouts. The custom order is preserved in the browser's `localStorage`.

Recommendation:

- Keep `get_dashboard_data()` as the only public dashboard entrypoint.
- Keep provider-specific fetch logic in private helpers (e.g. `_fetch_items`).

---

## 6. Book Context Menu Extension Contract

You can dynamically expose plugin items in the shared book context menu (dashboard/list/detail views).

Optional provider methods:

- `get_context_menu_items(self, db_type, context)`
- `run_context_menu_action(self, db_type, action_id, context)`

`get_context_menu_items()` example:

```python
def get_context_menu_items(self, db_type, context):
    return [
        {
            'id': 'open_vendor_search',
            'label': 'Search Title on Vendor Site',
            'icon': 'fa-solid fa-up-right-from-square',
        }
    ]
```

`run_context_menu_action()` return shape:

- Success: `{'success': True, 'message': '...', 'open_url': 'https://...'}`
- Failure: `{'success': False, 'error': '...'}`

Frontend rendering notes:

- Context menu items are automatically grouped by `plugin_name` with section headers/separators.
- If a plugin returns multiple actions, they are shown under the same plugin section.

Default `context` fields:

- `book_id`
- `book_title`
- `is_volume_detail`
- `library_id`

Core boundary:

- Core only handles shared endpoints/schema.
- Real menu definitions and behaviors stay inside plugins.

`stats_dashboard` context menu example:

- Item: `Show Reading Stats Summary`
- Action: reads current library stats and returns a toast message payload

### Sample: Naver Book Search Context Menu

A simple and useful starter plugin is one that opens an external search page from the current book title. It does not need an API key and works entirely through the context menu contract.

Sample file:

- [sample_plugins/metadata/naver_book/naver_book.py](../sample_plugins/metadata/naver_book/naver_book.py)

Core behavior:

- Read `book_id` and `book_title` from the context payload.
- Optionally re-fetch the latest `title` and `author` from `books` using `self.get_db_gateway(db_type)`.
- Return `open_url` from `run_context_menu_action()` to open Naver Book search in a new tab.

Example return payload:

```python
{
    'success': True,
    'message': 'Naver Book search page opens in a new tab.',
    'open_url': 'https://book.naver.com/search/search.naver?query=...'
}
```

## 7. Annotation (Highlight) Context Menu Extension Contract

Text selected in the EPUB/TXT reader can be saved as a highlight, and right-clicking (PC) or
long-pressing (mobile) a highlight opens a context menu that follows the exact same extension
pattern as the book context menu. The core only handles storing/anchoring/rendering highlights —
what to *do* with a highlight (export to Obsidian/Notion, sync to an external notes app, etc.) is
entirely up to plugins.

Optional provider methods:

- `get_annotation_context_menu_items(self, db_type, context)`
- `run_annotation_context_menu_action(self, db_type, action_id, context)`

Return shape is identical to the book context menu (see `get_context_menu_items`/`run_context_menu_action` above).

`context` fields:

- `annotation_id`
- `book_id`
- `book_title` — **always overwritten server-side with the current DB value**; the client-sent
  value is only a fallback used if the lookup fails, so don't rely on it being authoritative
- `series_name` — `null` for standalone (non-series) books
- `cover_image` — cover image URL normalized to an app-relative path (`/covers/...`), or `null` if none
- `format` (`epub` or `txt`)
- `chapter_idx` (`null` for TXT)
- `quote` — the highlighted source text
- `note` — user-entered note (`null` if none)
- `color`

> Core resolves `book_title`/`series_name`/`cover_image` itself by looking up `book_id` in the
> `books` table on every request — plugins don't need to re-query via
> `self.get_db_gateway(db_type)`. Because this project's file-naming convention usually already
> embeds the volume/episode number in the title (e.g. `05권`, `Chapter 1 ...`), `book_title` +
> `series_name` together are enough to identify which volume/episode a highlight came from without
> a separate numeric field.

Example:

```python
def get_annotation_context_menu_items(self, db_type, context):
    return [
        {
            'id': 'export_to_obsidian',
            'label': 'Export to Obsidian',
            'icon': 'fa-solid fa-file-export',
        }
    ]

def run_annotation_context_menu_action(self, db_type, action_id, context):
    if action_id != 'export_to_obsidian':
        return {'success': False, 'error': 'unknown action'}

    quote = context.get('quote', '')
    book_title = context.get('book_title', '')
    series_name = context.get('series_name') or book_title
    cover_image = context.get('cover_image')  # attach to note frontmatter if desired
    note_body = f"> {quote}\n\nSource: {series_name} — {book_title}"
    # e.g. use Obsidian's Advanced URI plugin obsidian:// scheme to create a new note
    obsidian_url = f"obsidian://new?vault=MyVault&content={note_body}"
    return {'success': True, 'message': 'Sent to Obsidian.', 'open_url': obsidian_url}
```

### Actions That Need User Input (`prompt` Response)

Some actions — like "let the user type their own note/annotation" — need text input before they can
run. `run_annotation_context_menu_action()` executes headlessly on the server so it cannot show an
input UI directly. Instead, return **a request asking the frontend to show one**; the frontend
displays a modal, collects the value, and **calls the same `action_id` again** — this time with
`context['prompt_value']` set to what the user typed. Check for the presence of `prompt_value` to
tell the "first call" apart from the "re-call with user input".

`prompt` request shape:

```python
{
    'success': True,
    'prompt': {
        'title': 'Add Note',
        'message': 'Write a note for this highlight.',  # optional
        'placeholder': 'Note content...',                # optional
        'default_value': '',                              # optional, pre-fill with an existing value
        'multiline': True,                                # optional, defaults to True (textarea)
        'submit_label': 'Save',                            # optional
    }
}
```

Full example — storing the note in **the plugin's own storage** (a JSONL file, a separate SQLite
database, whatever you like — not core's database):

```python
def get_annotation_context_menu_items(self, db_type, context):
    return [{'id': 'add_note', 'label': 'Add Note', 'icon': 'fa-solid fa-pen'}]

def run_annotation_context_menu_action(self, db_type, action_id, context):
    if action_id != 'add_note':
        return {'success': False, 'error': 'unknown action'}

    if 'prompt_value' not in context:
        # Step 1: no input yet, ask the frontend to show an input dialog
        return {
            'success': True,
            'prompt': {
                'title': 'Add Note',
                'placeholder': 'What do you think about this passage?',
                'default_value': self._load_note(context['annotation_id']) or '',
                'submit_label': 'Save',
            }
        }

    # Step 2: called again with the user's input — do the actual save here
    note_text = context['prompt_value']
    self._save_note(context['annotation_id'], note_text)  # e.g. append to JSONL, sqlite3 UPSERT, etc.
    return {'success': True, 'message': 'Note saved.', 'marker': '*'}
```

If the user clicks "Cancel" in the modal, no re-call happens — core handles that for you, so plugins
don't need to special-case cancellation.

### A Visual Indicator When Core Doesn't Know Where the Data Lives (`marker` Response Field)

If a note/annotation is stored in the plugin's own storage (JSONL, its own SQLite, etc.) instead of
the `note` column, core has no idea whether a given highlight has anything attached to it — it saves
fine but there's no way to tell from the reader UI, and no way to get back to it. To solve this,
include a `marker` key in `run_annotation_context_menu_action()`'s return value; core stores that
value in the `book_annotations.plugin_marker` column and renders it **as a superscript right after
the highlight**.

- A string value (e.g. `'*'`, `'📝'`) sets/updates the marker; an empty string or `None` clears it.
- Core does **not interpret the value's meaning** at all — it only handles "show something or not,
  and what to show." The actual note content still lives only in the plugin's own storage.
- If multiple plugins set a `marker` on the same highlight, the last write wins (there's no support
  yet for showing multiple plugins' markers side by side).
- Since `get_annotation_context_menu_items()` is called fresh every time the menu opens, checking your
  own storage there to swap the menu label based on state (e.g. "Add Note" ↔ "View/Edit Note") pairs
  naturally with this.

### Sample: Highlight Notes (prompt round-trip + JSONL storage)

A runnable sample plugin implementing the contract above end to end — `get_annotation_context_menu_items`/
`run_annotation_context_menu_action`, the two-step `prompt` round-trip, and a storage pattern that
appends notes to the plugin's own JSONL file instead of touching core's database.

Sample file:

- [sample_plugins/metadata/highlight_notes_sample/highlight_notes_sample.py](../sample_plugins/metadata/highlight_notes_sample/highlight_notes_sample.py)

Notes:

- The highlight CRUD REST API (`/api/v1/books/<book_id>/annotations`,
  `/api/v1/annotations/<annotation_id>`) only requires the logged-in session, so a plugin's
  `category_tab` webview UI can call it directly via `fetch()`. Use this for bulk features like
  "export all highlights in this book" without needing the context menu at all.
- Core does not proxy actual delivery to external services (API keys, OAuth, etc.) — opening that
  service's URI scheme/webhook via `open_url` is the simplest integration path.

### Webhook Integration (Recommended Modern Flow)

The recommended modern flow is configuring webhook targets from the **Plugin Settings UI**, not from `.env`.

In addition, the scanner emits `scan.new_books_detected` automatically when new books are found.

- payload: `db_type`, `library_id`, `library_name`, `new_books_count`, `sample_titles`
- `db_type` includes `audiobook` in addition to `general`/`adult`. The audiobook scanner (`services/audiobook_scanner.py`) is a separate pipeline, but it's wired to reuse the same `on_scan_new_books_detected` hook path, so new audiobooks are detected through the same plugin hook with no extra handling needed. See [spec_scanner_logic_en.md](./spec_scanner_logic_en.md#3-audiobook-scanner-a-fully-separate-pipeline) for the internal mechanics.

### Opt-in Activation for Private Plugins (ADD_PLUGIN, beta stage)

This convention was agreed with community developers. Anyone who can see the `plugins/metadata/` directory can see any plugin's code, so a private plugin (e.g. an in-house or paid plugin) distributed only to specific operators must **stay self-inactive unless the operator explicitly opts in**.

> ⚠️ This is currently in beta and supports exactly one fixed plugin_id: **`security-bookoasis-plugin`**. Any other plugin_id is ignored, and a multi-id allowlist is not supported yet (may be extended later if needed).

- The operator sets `ADD_PLUGIN=security-bookoasis-plugin` (exactly this value) either in `.env` or under `environment:` in `docker-compose.override.yml`.
- (Optional) Without touching the settings UI, storing the `ADD_PLUGIN` key directly in the DB `settings` table also works and takes precedence over the `.env` value.
- The plugin's own code must call the API below, at the point where it decides whether to activate (e.g. inside `on_scan_new_books_detected`, `get_dashboard_data`, `search`, or similar hook entry points), to check whether the configured `ADD_PLUGIN` value exactly matches its own fixed plugin_id. If it doesn't match, the plugin must do nothing and quietly return an empty result / `success: False`.

```
GET /api/media/plugins/add-plugin-check?plugin_id=security-bookoasis-plugin
```

Example response:

```json
{"success": true, "plugin_id": "security-bookoasis-plugin", "enabled": true}
```

- This API can be called without a login session (same public read-only nature as other plugin-bootstrap APIs).
- It only returns whether the queried `plugin_id` matches the fixed value — it never exposes the server's configured `ADD_PLUGIN` value itself.
- This gate is independent of the existing `PLUGIN_ENABLED_{id}` DB toggle (the admin UI's on/off switch). `ADD_PLUGIN` decides whether a plugin's existence is exposed at all, while `PLUGIN_ENABLED_{id}` handles the routine on/off state of a plugin that's already allowed to be exposed.

**Sample code**: start by copying [plugins/metadata/__template_add_plugin_gate.py](../plugins/metadata/__template_add_plugin_gate.py) as-is. Its filename starts with `__`, so it's excluded from plugin auto-discovery (same convention as the other template, `__template_dashboard_plugin.py`) and will never load as a real plugin while left in place. It shows `_is_add_plugin_enabled()` calling the API above, caching the result for 60 seconds, and always failing closed (treating errors/timeouts as disabled) — and demonstrates applying the same pattern to `search`/`apply` as well as hooks like `on_scan_new_books_detected`.

### New Books Webhook Notification Example Plugin

- Path: `sample_plugins/metadata/webhook_new_books_notify/webhook_new_books_notify.py`
- Behavior: after scan completes with new books, it sends notifications to configured multi webhook targets via `on_scan_new_books_detected`
- Supported formats: `discord`, `slack`, `telegram`, `generic`, `custom`
- Note: works from plugin settings only (no `.env` required).

How to use:

1. Enable plugin `신규도서 웹훅 알림` in Settings > Plugin Settings
2. Save `ENABLE_SCAN_WEBHOOK_NOTIFY=true`
3. Set `WEBHOOK_TARGETS_JSON`
4. (Optional) Adjust `CUSTOM_EVENT_PAYLOAD_JSON`, `MAX_SAMPLE_TITLES`, `REQUEST_TIMEOUT_SEC`
5. Run a library scan

Quick test URL validation:

1. Open `https://webhook.site` and generate a temporary endpoint URL
2. Add a test target in `WEBHOOK_TARGETS_JSON` like below
3. Run a scan and verify incoming JSON in webhook.site logs

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

Response-path validation test (httpbin):

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

Warning: do not send production secrets or sensitive payload data to public test endpoints.

### Standard Event Webhook Schema (book.new / book.read / book.finish)

For community integrations, the recommended standardized outbound event webhook contract is:

- Endpoint: `POST http://<server>/webhook`
- Events: `book.new`, `book.read`, `book.finish`
- Top-level keys: `event`, `user`, `Account`, `Metadata`

Example payload:

```json
{
    "event": "book.read",
    "user": true,
    "Account": {
        "id": 123456,
        "title": "username"
    },
    "Metadata": {
        "type": "book",
        "format": "epub",
        "title": "Book title",
        "author": "Author name",
        "publisher": "Publisher",
        "series": "Series name",
        "seriesIndex": null,
        "progress": 45,
        "totalPages": null,
        "currentLocation": "epubcfi(/6/2[chap01]!/4/2/14)",
        "addedAt": 1690000000
    }
}
```

Format constraints (important):

- EPUB/TXT do not always have stable physical pages, so `totalPages` may be `null`.
- Consumers should treat `progress` (0-100) as the primary progress signal.
- `currentLocation` should be interpreted by format:
    - EPUB: `href` / `cfi` / `spine`-based string
    - TXT: `chunk:N`
    - Fixed-page formats (PDF/ZIP/CBZ): `page:N`

Recommended consumer policy:

- Determine completion primarily by `book.finish` event or `progress`
- Treat `totalPages` as auxiliary metadata

### Standard Event Delivery Environment Variables

Core standardized event webhook delivery is controlled by:

- `WEBHOOK_EVENT_ENDPOINT` or `WEBHOOK_EVENT_ENDPOINTS`
- `WEBHOOK_EVENT_TIMEOUT`
- `WEBHOOK_EVENT_RETRY`
- `WEBHOOK_EVENT_SECRET` (HMAC signature header: `X-BookOasis-Signature`)

Notes:

- This can coexist with plugin-level `WEBHOOK_TARGETS_JSON` delivery.
- The standardized payload is intended to let plugin/integration developers implement receivers against one stable contract.

---

## 7. Plugin Developer Release Flow (With Auto-Update)

1. After code changes, bump `plugin version` in `VERSION`
2. Verify `update_manifest` path/file list matches actual repository layout
3. Push to GitHub and confirm files are reachable under `raw_base_url` (404 resolved)
4. Run sample update from Settings > Plugin Settings
5. Verify gate behavior: update only when `current < GitHub`, block otherwise

`WEBHOOK_TARGETS_JSON` example:

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

When `success_path` is set, the target is considered successful only if that JSON path is truthy.
(Example: `ok`, `result.success`)

---

## 7. Minimal Example

The two snippets below are copy-paste friendly baseline templates for both human and AI-assisted plugin development.

### Example A: Search-Type Metadata Plugin (Minimal)

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
        # Real plugins should persist updates through DB gateway APIs.
        return True, 'demo applied'
```

### Example B: Dashboard Widget Plugin (Minimal)

```python
# -*- coding: utf-8 -*-
from plugins.metadata.base import BaseMetadataProvider


class MyWidgetMetadataProvider(BaseMetadataProvider):
    id = "my_widget"
    name = "My Widget"
    is_searchable = False
    config_schema = []
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
        return False, "Dashboard-only plugin"

    def _fetch_items(self, db_type, limit=10):
        return {'success': True, 'items': []}

    def get_dashboard_data(self, db_type, limit=10):
        return self._fetch_items(db_type, limit=limit)
```

If your plugin supports updates, declare `update_manifest` inside the class as shown above,
and keep `"plugin version"` in the plugin root `VERSION` file.

### Plugin DB Gateway (Recommended)

Do not open DB connections with direct `import database` in plugins.
Use provider helpers instead:

- `self.get_db_gateway(db_type)`
- `self.get_plugin_config(db_type, default={})`

Gateway methods:

- `fetch_one(query, params=())`
- `fetch_all(query, params=())`
- `execute(query, params=())`
- `execute_many(query, seq_of_params)`
- `transaction()`
- `get_setting(key, default=None)` / `set_setting(key, value)`

Example:

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

## 8. Activation Flow

1. Add plugin files under `plugins/metadata/`.
2. Restart the server.
3. Go to Settings > Plugin Settings.
4. Enable the plugin and save config values.
5. If `is_searchable=True`, it appears in manual metadata search modal.
6. If `dashboard_widget` + `get_dashboard_data()` are implemented, it appears in dashboard widgets automatically.

---

## 9. Statistics Plugin Example (Same Requirements)

Example plugin: `sample_plugins/metadata/stats_dashboard/stats_dashboard.py`

Dashboard items:

1. Total: series count / book count
2. Books read (100% completed): this week 00 books / this month 00 books
3. Newly added books: this week 00 books / this month 00 books

Implementation points:

- Define `dashboard_widget` to expose the widget card
- Return the three metrics in `items` from `get_dashboard_data()` (with weekly/monthly aggregation)
- Extend behavior inside plugin SQL/logic only, without core modifications

Note:

- These statistics items (total/weekly/monthly) are defined in the plugin.
- The core only consumes shared contracts (`dashboard_widget`, `get_dashboard_data`), so changing items does not require core changes.

---

## 10. 🌐 External Domain Webview & Download API

Core-provided API for plugins that need to show an external site inside the app, or download a file from an external URL into a library.

**Responsibility**: BookOasis does not provide or recommend any external domain by default. This API only works for domains **the user has explicitly registered** in their own [Settings > External Domains] tab whitelist. Plugins cannot add or bypass this whitelist — registering and using a domain is entirely the user's own responsibility.

### `window.BookOasisPlugin.openWebview(url)`

Fetches the URL through a server-side proxy and displays it in an in-app modal (iframe).

```js
window.BookOasisPlugin.openWebview('https://example.com/some-page');
```

- If the host isn't in the current user's whitelist, only an error toast is shown and nothing opens. Matching is **exact** — registering `example.com` does NOT cover `www.example.com` (treated as a different host); use a wildcard entry like `*.example.com` to cover subdomains.
- The server performs SSRF defense (blocks private/loopback IPs, re-validates every redirect hop, caps response size at 15MB), so some requests may still be rejected even for whitelisted domains.
- If the response is HTML, a `<base href="original-site">` tag is auto-injected so relative image/CSS/JS/link URLs resolve against the original site instead of the proxy. This isn't a full asset rewriter (e.g. inline `style="background:url(...)"` isn't handled), so heavy SPA-style sites may still render incorrectly.

### `window.BookOasisPlugin.downloadToLibrary(url, { libraryId, dbType })`

Downloads the file at the URL, saves it into the selected library's physical path, and immediately triggers a scan to import it.

```js
window.BookOasisPlugin.downloadToLibrary('https://example.com/book.epub', {
  libraryId: 12,
  dbType: 'general' // defaults to 'general' if omitted
});
```

- Goes through the same whitelist check + SSRF defense (500MB response cap).
- Fails if the calling user doesn't have access to the target library.
- If the extension isn't one of the supported formats (`.zip .cbz .epub .pdf .txt`), the file is still saved but not imported as a book (`imported_as_book: false`).
- Returns a Promise resolving to `{ success, filename, imported_as_book, warning?, scan_error? }`.

You don't need to implement your own download/proxy logic in the plugin's Python backend — reuse these two APIs instead. See the reference implementation below for a working example.

### Reference implementation: the `gutenberg_browser` sample plugin

- Path: `sample_plugins/metadata/gutenberg_browser/`
- Registers a first-class sidebar menu via `category_tab`, and its `index.html`/`script.js` demonstrate both `openWebview()` (opens the Project Gutenberg website) and `downloadToLibrary()` (downloads a user-entered URL into a chosen library).
- See how it populates its library `<select>` via `GET /api/media/libraries?type=general`.

---

## 💡 Tip: Handling iframe Security Constraints
When embedding external web services inside a custom plugin tab or card using `<iframe>`, you should be aware of security constraints enforced by browsers.

1. **X-Frame-Options & CSP Blockage**:
   - Websites that configure `X-Frame-Options: SAMEORIGIN` or restrictive `Content-Security-Policy` headers (e.g., Google, Naver, GitHub) **cannot** be rendered inside an iframe on third-party sites.
   - **Solution**: You no longer need to build your own proxy route — use `window.BookOasisPlugin.openWebview()` from §10 above, which already implements the proxy and header stripping.
2. **Mixed Content Blockage**:
   - If BookOasis is served over SSL (HTTPS), all iframe source URLs must also use `https://`. Unencrypted `http://` resources will be automatically blocked by modern web browsers.
