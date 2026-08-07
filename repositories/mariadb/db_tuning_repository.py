# -*- coding: utf-8 -*-
"""
db_tuning_repository.py – MariaDB 전용 데이터베이스 튜닝 및 최적화(OPTIMIZE/ANALYZE TABLE) 데이터 액세스 레이어
"""
import database

class DbTuningRepository:
    @staticmethod
    def run_sqlite_optimize(db_type):
        """MariaDB 전용 데이터베이스 테이블 성능 최적화 명령어 실행"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("ANALYZE TABLE books, libraries, user_progress, scanner_tasks, settings;")
            cursor.execute("OPTIMIZE TABLE books, libraries, user_progress, scanner_tasks, settings;")
            conn.commit()
        except Exception as e:
            print(f"[DbTuningRepository WARNING] MariaDB OPTIMIZE/ANALYZE failed: {e}")
        finally:
            conn.close()
