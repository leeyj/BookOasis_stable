# -*- coding: utf-8 -*-
"""
Dashboard plugin template (copy this file and rename it, do not import directly).

Why this filename starts with '__':
- MetadataFactory discovery skips files/folders starting with '__'.
- This template will never be loaded as a runtime plugin.
"""

import json
import urllib.parse
import urllib.request

from plugins.metadata.base import BaseMetadataProvider


class ExampleDashboardMetadataProvider(BaseMetadataProvider):
    """Example provider template for dashboard-only plugins."""

    # Plugin identity
    id = "example_dashboard"
    name = "예시 대시보드 위젯"

    # Set True only when you want this plugin selectable in manual metadata search UI.
    # Current settings page visibility follows this field.
    is_searchable = True

    # Optional settings schema (stored as JSON in settings.PLUGIN_CONFIG_<id>)
    config_schema = [
        {
            "key": "API_KEY",
            "label": "외부 API Key",
            "type": "text",
            "required": True,
            "description": "외부 데이터 소스 인증 키"
        }
    ]

    # Dashboard widget metadata consumed by core API/UI
    dashboard_widget = {
        "title": "예시 위젯",
        "subtitle": "플러그인에서 직접 렌더 데이터 제공",
        "provider": "Example",
        "icon": "fa-solid fa-puzzle-piece",
        "limit": 10,
    }

    def _get_api_key(self, db_type):
        try:
            cfg = self.get_plugin_config(db_type, default={})
            if isinstance(cfg, dict):
                return cfg.get("API_KEY")
        except Exception:
            pass
        return None

    # Required by BaseMetadataProvider: no-op for dashboard-only plugin
    def search(self, db_type, query):
        return []

    # Required by BaseMetadataProvider: no-op for dashboard-only plugin
    def apply(self, db_type, book_id, item_data):
        return False, "대시보드 전용 플러그인은 메타데이터 적용을 지원하지 않습니다."

    def _fetch_items(self, db_type, limit=10):
        """
        Plugin-internal data fetch helper.
        Return shape:
        - {'success': True, 'items': [...]}
        - {'success': False, 'error': '...'}
        """
        api_key = self._get_api_key(db_type)
        if not api_key:
            return {"success": False, "error": "API_KEY가 설정되지 않았습니다."}

        # Replace this with your real API endpoint.
        url = "https://example.com/api/items"
        params = {
            "api_key": api_key,
            "limit": int(limit or 10),
        }

        try:
            query_string = urllib.parse.urlencode(params)
            req = urllib.request.Request(
                f"{url}?{query_string}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))

            raw_items = payload.get("items", []) if isinstance(payload, dict) else []
            items = []
            for r in raw_items:
                items.append(
                    {
                        "title": r.get("title", ""),
                        "author": r.get("author", ""),
                        "publisher": r.get("publisher", ""),
                        "pubDate": r.get("pubDate", ""),
                        "cover": r.get("cover", ""),
                        "description": r.get("description", ""),
                        "link": r.get("link", ""),
                    }
                )
            return {"success": True, "items": items}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Core contract for dashboard loader
    def get_dashboard_data(self, db_type, limit=10):
        return self._fetch_items(db_type, limit=limit)
