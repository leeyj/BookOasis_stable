# 🧩 Metadata Plugin Development Guide (New Standard)

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
    index.html      # optional: custom settings UI
    style.css       # optional: custom settings styles
    script.js       # optional: custom settings initializer
```

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

Required methods:

- `search(self, db_type, query)`
- `apply(self, db_type, book_id, item_data)`

Dashboard method (for widget plugins):

- `get_dashboard_data(self, db_type, limit=10)`

Return shape:

- Success: `{'success': True, 'items': [...]}`
- Failure: `{'success': False, 'error': '...'}`

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
