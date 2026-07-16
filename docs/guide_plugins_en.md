# 🧩 Plugin Development Guide (New Standard)

This document describes the current plugin standard for BookOasis metadata/dashboard plugins.

> Scope: external provider plugins under `plugins/metadata/`.
> For scanner parser modules, use [guide_scanner_parser.md](./guide_scanner_parser.md).

---

## 1. Core Principle

- The core must not know plugin-specific names, routes, or internal helper methods.
- The core only relies on shared contracts.
- Plugin extension should be completed inside `plugins/metadata/` without core code forks.

---

## 2. Directory Structure

Folder-based layout is recommended.

```text
plugins/metadata/
  my_widget/
    __init__.py
    my_widget.py
        VERSION         # required for auto-update support
    index.html      # optional: custom settings UI
    style.css       # optional: custom settings styles
    script.js       # optional: custom settings initializer
```

### Version File Contract for Auto-Update Support (Required)

To be eligible for GitHub-based plugin auto-update support, each plugin must include a `VERSION` file at the plugin root with the key below.

```json
{
    "plugin version": "1.0.0"
}
```

Policy:

- Key name must be exactly `plugin version` (with a space)
- SemVer format is recommended (`MAJOR.MINOR.PATCH`)
- If missing, the plugin is excluded from auto-update support
- Legacy key (`plugin_version`) may be parsed for backward compatibility, but new/official plugins must use `plugin version`

Legacy single-file modules are still loadable, but new development should use folder-based modules.

Quick start template:

- Copy `plugins/metadata/__template_dashboard_plugin.py`
- Rename module/class/id to your plugin identity

---

## 3. Provider Contract

All providers must inherit [plugins/metadata/base.py](../plugins/metadata/base.py).

Recommended class attributes:

- `id` (str): plugin identifier
- `name` (str): display name
- `is_searchable` (bool): show in manual metadata search modal
- `config_schema` (list): settings form schema
- `dashboard_widget` (dict or None): dashboard widget metadata (common desk card or exclusive full-screen tab configurations)
- `update_manifest` (dict or None): plugin-owned update declaration contract

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

- [plugins/metadata/naver_book/naver_book.py](../plugins/metadata/naver_book/naver_book.py)

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

### Webhook Integration (Recommended Modern Flow)

The recommended modern flow is configuring webhook targets from the **Plugin Settings UI**, not from `.env`.

In addition, the scanner emits `scan.new_books_detected` automatically when new books are found.

- payload: `db_type`, `library_id`, `library_name`, `new_books_count`, `sample_titles`

### New Books Webhook Notification Example Plugin

- Path: `plugins/metadata/webhook_new_books_notify/webhook_new_books_notify.py`
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

Example plugin: `plugins/metadata/stats_dashboard/stats_dashboard.py`

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

## 💡 Tip: Handling iframe Security Constraints
When embedding external web services inside a custom plugin tab or card using `<iframe>`, you should be aware of security constraints enforced by browsers.

1. **X-Frame-Options & CSP Blockage**:
   - Websites that configure `X-Frame-Options: SAMEORIGIN` or restrictive `Content-Security-Policy` headers (e.g., Google, Naver, GitHub) **cannot** be rendered inside an iframe on third-party sites.
   - **Solution**: Implement a reverse proxy route in your plugin's python backend (using `requests` to fetch the external page and stripping off the restrictive headers before returning it to the browser), or simply open the link in a new tab via `target="_blank"`.
2. **Mixed Content Blockage**:
   - If BookOasis is served over SSL (HTTPS), all iframe source URLs must also use `https://`. Unencrypted `http://` resources will be automatically blocked by modern web browsers.
