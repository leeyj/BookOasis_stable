# -*- coding: utf-8 -*-
import json
from repositories.plugin_repository import PluginRepository
from repositories.metadata_repository import MetadataRepository

class PluginDatabaseGateway:
    """Shared DB gateway for metadata plugins."""

    def __init__(self, db_type="general"):
        self.db_type = db_type or "general"

    def fetch_one(self, query, params=()):
        rows = PluginRepository.execute_custom_query(self.db_type, query, params, commit=False)
        return rows[0] if rows else None

    def fetch_all(self, query, params=()):
        return PluginRepository.execute_custom_query(self.db_type, query, params, commit=False)

    def execute(self, query, params=()):
        return PluginRepository.execute_custom_query(self.db_type, query, params, commit=True)

    def execute_many(self, query, seq_of_params):
        rowcount = 0
        for params in seq_of_params:
            rowcount += PluginRepository.execute_custom_query(self.db_type, query, params, commit=True)
        return rowcount

    def get_setting(self, key, default=None):
        val = MetadataRepository.get_setting_value(self.db_type, key)
        if val is None:
            return default
        return {"value": val}

    def set_setting(self, key, value):
        PluginRepository.save_plugin_setting(self.db_type, key, str(value))

    def get_plugin_config(self, plugin_id, default=None):
        raw_row = self.get_setting(f"PLUGIN_CONFIG_{plugin_id}", None)
        if raw_row is None:
            return {} if default is None else default
        raw = raw_row["value"]
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else ({} if default is None else default)
        except Exception:
            return {} if default is None else default

    def set_plugin_config(self, plugin_id, config):
        data = config if isinstance(config, dict) else {}
        self.set_setting(f"PLUGIN_CONFIG_{plugin_id}", json.dumps(data, ensure_ascii=False))
