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

## 7. Auto-Update Contract (Plugin-Owned Declaration)

- Auto-update behavior must be declared by the plugin class via `update_manifest`, not core hardcoding.
- If auto-update is supported, the plugin root `VERSION` file must include `"plugin version"`.

Checklist:

- Is `update_manifest.enabled = True`?
- Is `provider = "github-raw"`?
- Does `raw_base_url` match the real GitHub raw path?
- Does `files` include all deploy files and `VERSION`?
- Is `version_key` set to `plugin version`?
- Does the gate allow updates only when `current version < GitHub version`?

---

## 8. Error Prevention

- Check for import errors.
- Make sure class names and file names match discovery rules.
- Avoid duplicate `id` values.
- Do not commit `__pycache__` in plugin folders.

Common failure cases:

- `ImportError`: loader discovery fails due to folder/file/class naming mismatch
- `id` collision: duplicate plugin `id`
- Invalid `config_schema`: missing keys/types causing settings UI render failures
- `update_manifest` typo: sample update button hidden or update failure
- Webhook signature mismatch: receiver returns 401/403 due to invalid `WEBHOOK_EVENT_SECRET`
- EPUB/TXT progress assumption bug: parser fails when `totalPages` is nullable

---

## 9. Minimum Validation

After adding the plugin, verify in this order:

1. Restart the server
2. Confirm it appears in `MetadataFactory.get_available_providers()`
3. For dashboard widgets, check `/api/media/dashboard/widgets`
4. For context menu actions, check `/api/media/context-menu/book/plugins`
5. Confirm plugin data calls work without 500 errors
6. (For update-enabled plugins) verify `sample-update` responses for 404 and version gate messages behave as expected

---

## 10. Standard Event Webhook Validation (book.new/read/finish)

If you rely on standardized community event webhooks, verify the following:

- Environment variables are configured correctly:
	- `WEBHOOK_EVENT_ENDPOINT` or `WEBHOOK_EVENT_ENDPOINTS`
	- `WEBHOOK_EVENT_TIMEOUT`, `WEBHOOK_EVENT_RETRY`
	- (Optional) `WEBHOOK_EVENT_SECRET`
- `book.new`, `book.read`, and `book.finish` are all emitted as expected
- Payload keeps top-level schema: `event`, `user`, `Account`, `Metadata`
- If signature is enabled, receiver validates `X-BookOasis-Signature`

Format-constraint validation (important):

- Receiver logic still works when `totalPages` is `null` for EPUB/TXT
- EPUB/TXT progress handling is based on `Metadata.progress` (0-100), not page count
- Receiver can parse `Metadata.currentLocation` by format:
	- EPUB: `href` / `cfi` / `spine` string
	- TXT: `chunk:N`
	- PDF/ZIP/CBZ: `page:N`

---

## 11. CI-Friendly Fixed Validation Scenario

Automating the sequence below provides fast regression coverage for plugin and webhook behavior.

1. Start server and verify `/api/media/dashboard/widgets` returns 200 with JSON `success=true`
2. Enable target plugin and verify its `id` appears in `/api/media/metadata/plugins`
3. Scan one test book and verify one `book.new` event is received
4. Call viewer progress save (`/api/media/progress`) and verify `book.read` event is received
5. Update progress to completion transition and verify `book.finish` is emitted once
6. If signature is enabled, verify `X-BookOasis-Signature` HMAC validation passes

Expected results:

- Each step returns HTTP 2xx or documented success payload
- `book.finish` is emitted exactly once at completion transition per book/user pair
- EPUB/TXT event parsing remains stable even when `totalPages` is nullable
