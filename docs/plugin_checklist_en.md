# Plugin Writing Checklist

Use this checklist when adding a new metadata or dashboard plugin.

---

## 1. Location and Naming

- Place the plugin under `plugins/metadata/`.
- Prefer a folder-based layout.
- Keep folder name, file name, class name, and `id` aligned.

Example:

- `plugins/metadata/my_plugin/my_plugin.py`
- `class MyPluginMetadataProvider(BaseMetadataProvider)`
- `id = "my_plugin"`

---

## 2. Required Base Class

- Inherit from `BaseMetadataProvider`.
- Implement both `search()` and `apply()`.

---

## 3. DB Access Rules

- Do not use `import database` directly inside plugins.
- Use `self.get_db_gateway(db_type)`.
- Read plugin config with `self.get_plugin_config(db_type, default={})`.

Recommended gateway methods:

- `fetch_one()`
- `fetch_all()`
- `execute()`
- `execute_many()`
- `transaction()`

---

## 4. Dashboard Plugins

To show a widget on the dashboard, implement:

- `dashboard_widget`
- `get_dashboard_data()`

Checklist:

- Does `get_dashboard_data()` return `{'success': True, 'items': [...]}`?
- Can it handle both metric cards and regular items?
- Does it respect the `limit` argument?

---

## 5. Context Menu Plugins

To add book context menu actions, implement:

- `get_context_menu_items()`
- `run_context_menu_action()`

Checklist:

- Are `id` and `label` non-empty?
- Does the return value follow the `success / error` contract?
- Return `open_url` when needed.

---

## 6. Settings and Activation

- Decide whether `config_schema` is needed.
- Save config under `PLUGIN_CONFIG_<id>`.
- Enable state uses `PLUGIN_ENABLED_<id>`.

Checklist:

- Is the plugin enabled by default?
- Does it fail safely when config JSON is invalid?

---

## 7. Error Prevention

- Check for import errors.
- Make sure class names and file names match discovery rules.
- Avoid duplicate `id` values.
- Do not commit `__pycache__` in plugin folders.

---

## 8. Minimum Validation

After adding the plugin, verify in this order:

1. Restart the server
2. Confirm it appears in `MetadataFactory.get_available_providers()`
3. For dashboard widgets, check `/api/media/dashboard/widgets`
4. For context menu actions, check `/api/media/context-menu/book/plugins`
5. Confirm plugin data calls work without 500 errors
