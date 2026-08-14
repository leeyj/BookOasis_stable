# -*- coding: utf-8 -*-
"""
plugin_repository.py – 플러그인 전용 데이터 보존 및 플러그인 게이트웨이 SQL 데이터 액세스 레이어
"""
import database

class PluginRepository:
    @staticmethod
    def save_plugin_setting(db_type, key, value):
        """설정(settings) 테이블에 플러그인 활성 상태나 설정값 저장"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def record_load_event(db_type, plugin_id, status, message=None):
        """플러그인 로드 시도 결과(성공/실패)를 이력으로 기록"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO plugin_load_events (plugin_id, status, message) VALUES (?, ?, ?)",
                (plugin_id, status, message)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_latest_load_status(db_type):
        """플러그인별 가장 최근 로드 시도 상태 1건씩 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.plugin_id, e.status, e.message, e.occurred_at
            FROM plugin_load_events e
            INNER JOIN (
                SELECT plugin_id, MAX(id) AS max_id
                FROM plugin_load_events
                GROUP BY plugin_id
            ) latest ON latest.plugin_id = e.plugin_id AND latest.max_id = e.id
            ORDER BY e.occurred_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def prune_stale_load_events(db_type, valid_plugin_ids):
        """더 이상 plugins/metadata 디렉토리에 존재하지 않는 플러그인의 과거 로드 이력을 정리합니다.
        (폴더를 삭제해도 마지막 실패 기록이 영구히 남아 계속 '실패'로 표시되는 문제 방지)"""
        valid_ids = list(valid_plugin_ids or [])
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if valid_ids:
                placeholders = ','.join('?' for _ in valid_ids)
                cursor.execute(
                    f"DELETE FROM plugin_load_events WHERE plugin_id NOT IN ({placeholders})",
                    valid_ids
                )
            else:
                cursor.execute("DELETE FROM plugin_load_events")
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_recent_load_events(db_type, limit=100):
        """최근 플러그인 로드 이력(상태 변화 포함) 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT plugin_id, status, message, occurred_at FROM plugin_load_events ORDER BY occurred_at DESC, id DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def execute_custom_query(db_type, query, params=None, commit=False):
        """플러그인에서 게이트웨이를 경유해 직접 호출하는 가변 질의문 실행기"""
        if params is None:
            params = ()
            
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if commit:
                cursor.execute("BEGIN")
                cursor.execute(query, params)
                rowcount = cursor.rowcount
                conn.commit()
                return rowcount
            else:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            if commit:
                conn.rollback()
            raise e
        finally:
            conn.close()
