# -*- coding: utf-8 -*-
import json
from contextlib import contextmanager

import database


class PluginDatabaseGateway:
    """Shared DB gateway for metadata plugins."""

    def __init__(self, db_type="general"):
        self.db_type = db_type or "general"

    @contextmanager
    def connection(self):
        conn = database.get_connection(self.db_type)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self.connection() as conn:
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def fetch_one(self, query, params=()):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()

    def fetch_all(self, query, params=()):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute(self, query, params=()):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount

    def execute_many(self, query, seq_of_params):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, seq_of_params)
            conn.commit()
            return cursor.rowcount

    def get_setting(self, key, default=None):
        row = self.fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
        if not row:
            return default
        return row["value"]

    def set_setting(self, key, value):
        self.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )

    def get_plugin_config(self, plugin_id, default=None):
        raw = self.get_setting(f"PLUGIN_CONFIG_{plugin_id}", None)
        if raw is None:
            return {} if default is None else default
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else ({} if default is None else default)
        except Exception:
            return {} if default is None else default

    def set_plugin_config(self, plugin_id, config):
        data = config if isinstance(config, dict) else {}
        self.set_setting(f"PLUGIN_CONFIG_{plugin_id}", json.dumps(data, ensure_ascii=False))
