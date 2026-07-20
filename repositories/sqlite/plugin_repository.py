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
