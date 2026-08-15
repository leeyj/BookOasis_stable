# -*- coding: utf-8 -*-
"""
Private plugin self-gating template (copy this file and rename it, do not import directly).

Why this filename starts with '__':
- MetadataFactory discovery skips files/folders starting with '__'.
- This template will never be loaded as a runtime plugin.

What this template demonstrates:
- The ADD_PLUGIN opt-in convention agreed with community developers for PRIVATE plugins
  (plugins whose existence/behavior should stay dormant unless the operator explicitly
  enables them via ADD_PLUGIN in .env / docker-compose override / DB settings).
- The plugin calls GET /api/media/plugins/add-plugin-check?plugin_id=<own id> itself and
  only proceeds when the response says enabled=True. If not enabled, every hook must do
  nothing and return a quiet "skipped" result — never raise, never log the check as an error.
- Beta-stage note: today the server only recognizes ADD_PLUGIN == "security-bookoasis-plugin".
  Any other plugin_id will always come back enabled=False. See docs/guide_plugins.md
  ("비공개(private) 플러그인 선택적 활성화 (ADD_PLUGIN, 베타 테스트 단계)") for the current
  status of this convention and how it may be extended later.

This template is a normal metadata-search plugin (search/apply) that additionally reacts to
the scan-completion hook, but the gating pattern below (`_is_add_plugin_enabled`) applies the
same way to any hook: get_dashboard_data, get_context_menu_items, on_scan_new_books_detected, etc.
"""

import os
import time

from plugins.metadata.base import BaseMetadataProvider

try:
    import requests
except ImportError:
    requests = None


class ExampleAddPluginGatedMetadataProvider(BaseMetadataProvider):
    """Example provider template for a private plugin gated by ADD_PLUGIN."""

    # Plugin identity — must match the id checked against ADD_PLUGIN.
    # Rename this to your own private plugin's id when you copy this template.
    id = "security-bookoasis-plugin"
    name = "예시 비공개 플러그인 (ADD_PLUGIN 게이트)"
    is_searchable = True
    config_schema = []

    # Cache the add-plugin-check result briefly so every hook call doesn't
    # round-trip to the API. Adjust TTL to taste; 0 disables caching.
    _ADD_PLUGIN_CACHE_TTL_SEC = 60.0
    _add_plugin_cache = None  # {'checked_at': float, 'enabled': bool}

    def _server_base_url(self):
        """Build a same-host base URL to call the server's own public API.
        This plugin runs in-process on the same server, so localhost + PORT
        (matching docker-compose's PORT env var, default 5930) is enough —
        no external hostname/TLS setup needed."""
        port = os.environ.get("PORT", "5930")
        return f"http://127.0.0.1:{port}"

    def _is_add_plugin_enabled(self, force_refresh=False):
        """Check ADD_PLUGIN activation for this plugin's own id via the public API.
        Fails closed: any error, timeout, or non-200 response is treated as disabled."""
        now = time.monotonic()
        cached = self._add_plugin_cache
        if (
            not force_refresh
            and cached
            and (now - cached["checked_at"]) <= self._ADD_PLUGIN_CACHE_TTL_SEC
        ):
            return cached["enabled"]

        enabled = False
        if requests is not None:
            try:
                resp = requests.get(
                    f"{self._server_base_url()}/api/media/plugins/add-plugin-check",
                    params={"plugin_id": self.id},
                    timeout=3,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    enabled = bool(data.get("success") and data.get("enabled"))
            except Exception:
                # Fail closed: network hiccups must never accidentally enable
                # behavior meant to stay off unless the operator opted in.
                enabled = False

        self._add_plugin_cache = {"checked_at": now, "enabled": enabled}
        return enabled

    # ── Required BaseMetadataProvider contract ──
    def search(self, db_type, query):
        if not self._is_add_plugin_enabled():
            return []
        # Your private search logic goes here.
        return []

    def apply(self, db_type, book_id, item_data):
        if not self._is_add_plugin_enabled():
            return False, "이 플러그인은 ADD_PLUGIN으로 활성화되지 않았습니다."
        # Your private apply logic goes here.
        return False, "not implemented"

    # ── Optional hook example: scanner new-book event ──
    def on_scan_new_books_detected(self, db_type, payload):
        if not self._is_add_plugin_enabled():
            # Quiet no-op — this is the expected, normal state for anyone
            # who hasn't set ADD_PLUGIN=security-bookoasis-plugin.
            return {
                "success": True,
                "skipped": True,
                "message": "ADD_PLUGIN not set to this plugin's id; staying inactive.",
            }

        # Your private on-scan logic goes here.
        return {"success": True, "skipped": False}
