# -*- coding: utf-8 -*-
"""
db_tuning_repository.py – 데이터베이스 튜닝 및 최적화(VACUUM, REINDEX 등) 전담 데이터 액세스 레이어
"""
import database

class DbTuningRepository:
    @staticmethod
    def run_sqlite_optimize(db_type):
        """SQLite 전용 데이터베이스 성능 최적화 명령어 실행"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            # 1. 통계 및 인덱스 재생성
            cursor.execute("ANALYZE;")
            cursor.execute("REINDEX;")
            conn.commit()
        except Exception as e:
            print(f"[DbTuningRepository WARNING] SQLite ANALYZE/REINDEX failed: {e}")
        finally:
            conn.close()

        # 2. VACUUM (독립 트랜잭션에서 무조건 실행해야 하므로 별개로 연결 획득)
        conn_vacuum = database.get_connection(db_type)
        try:
            conn_vacuum.execute("VACUUM;")
        except Exception as e:
            print(f"[DbTuningRepository WARNING] SQLite VACUUM failed: {e}")
        finally:
            conn_vacuum.close()
