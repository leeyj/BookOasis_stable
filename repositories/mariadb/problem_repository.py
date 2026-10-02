# -*- coding: utf-8 -*-
"""
problem_repository.py – MariaDB 전용 문제 기록(알림센터 문제 카드) 데이터 액세스 레이어

problem_occurrences: 대상 1개 x 코드 1개 = 1행. 재발하면 횟수/마지막 시각만 늘어난다(UPSERT).
problem_groups: 카드(group_key) 단위 상태(알고 있음/음소거).
settings와 같이 general DB 하나에 모은다 - 대상의 DB는 db_type 컬럼으로 구분한다.
시각은 DB 시간대 차이가 없는 epoch ms.
"""
import database

_CHUNK = 500

_SEVERITY_RANK_SQL = (
    "MAX(CASE severity WHEN 'action_required' THEN 2 WHEN 'notice' THEN 1 ELSE 0 END)"
)

# 열린 행이 하나도 없는 카드의 음소거 상태를 지운다 - 남겨 두면 나중에 같은 카드가 다시 생겼을 때
# 예전 muted_count에 가려 안 보일 수 있다.
_CLEAR_EMPTY_GROUPS_SQL = (
    "DELETE FROM problem_groups WHERE group_key NOT IN "
    "(SELECT DISTINCT group_key FROM problem_occurrences WHERE status = 'open')"
)


class ProblemRepository:
    @staticmethod
    def upsert(row, now_ms):
        """같은 (code, db_type, target_type, target_id)가 있으면 횟수/마지막 시각만 갱신한다.

        해결됐던 행이 다시 발생하면 새 문제로 본다: 횟수 1, 최초 시각을 지금으로 되돌린다
        (resolved_ms는 '마지막 정상 시각'으로 남겨 둔다)."""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO problem_occurrences (
                    code, severity, source, db_type, library_id, target_type, target_id, target_path,
                    series_key, group_key, title, detail, message, context,
                    occurrence_count, first_seen_ms, last_seen_ms, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, 'open')
                ON DUPLICATE KEY UPDATE
                    -- MariaDB는 대입을 왼쪽부터 적용하므로 status를 바꾸기 전에 이전 status를 본다.
                    occurrence_count = IF(status = 'open', occurrence_count + 1, 1),
                    first_seen_ms = IF(status = 'open', first_seen_ms, VALUES(first_seen_ms)),
                    last_seen_ms = VALUES(last_seen_ms),
                    status = 'open',
                    severity = VALUES(severity),
                    source = VALUES(source),
                    library_id = VALUES(library_id),
                    target_path = VALUES(target_path),
                    series_key = VALUES(series_key),
                    group_key = VALUES(group_key),
                    title = VALUES(title),
                    detail = VALUES(detail),
                    message = VALUES(message),
                    context = VALUES(context)
                """,
                (
                    row['code'], row['severity'], row['source'], row['db_type'], row.get('library_id'),
                    row['target_type'], row['target_id'], row.get('target_path'),
                    row.get('series_key'), row['group_key'], row.get('title'), row.get('detail'),
                    row.get('message'), row.get('context'), now_ms, now_ms,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get(code, db_type, target_type, target_id):
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM problem_occurrences WHERE code = %s AND db_type = %s AND target_type = %s AND target_id = %s",
                (code, db_type, target_type, target_id),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def resolve(code, db_type, target_type, target_id, now_ms):
        """열린 행 하나를 해결 처리한다. 바뀐 행 수(0/1)를 돌려준다."""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE problem_occurrences SET status = 'resolved', resolved_ms = %s "
                "WHERE code = %s AND db_type = %s AND target_type = %s AND target_id = %s AND status = 'open'",
                (now_ms, code, db_type, target_type, target_id),
            )
            changed = cursor.rowcount or 0
            if changed:
                cursor.execute(_CLEAR_EMPTY_GROUPS_SQL)
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def resolve_targets(db_type, target_type, target_ids, now_ms, code=None):
        """여러 대상의 열린 행을 한꺼번에 해결 처리한다 (code를 주면 그 코드만)."""
        ids = [str(t) for t in (target_ids or [])]
        if not ids:
            return 0
        conn = database.get_connection('general')
        cursor = conn.cursor()
        changed = 0
        try:
            for i in range(0, len(ids), _CHUNK):
                chunk = ids[i:i + _CHUNK]
                placeholders = ','.join(['%s'] * len(chunk))
                sql = (
                    "UPDATE problem_occurrences SET status = 'resolved', resolved_ms = %s "
                    f"WHERE db_type = %s AND target_type = %s AND target_id IN ({placeholders}) AND status = 'open'"
                )
                params = [now_ms, db_type, target_type, *chunk]
                if code:
                    sql += " AND code = %s"
                    params.append(code)
                cursor.execute(sql, params)
                changed += cursor.rowcount or 0
            if changed:
                cursor.execute(_CLEAR_EMPTY_GROUPS_SQL)
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def list_open(target_type=None, code=None):
        sql = "SELECT * FROM problem_occurrences WHERE status = 'open'"
        params = []
        if target_type:
            sql += " AND target_type = %s"
            params.append(target_type)
        if code:
            sql += " AND code = %s"
            params.append(code)
        sql += " ORDER BY target_id"
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_open_for_library(db_type, library_id, codes=None):
        """한 카테고리의 열린 행 (스캔 끝 정리/일괄 조치용)."""
        sql = "SELECT * FROM problem_occurrences WHERE status = 'open' AND db_type = %s AND library_id = %s"
        params = [db_type, int(library_id)]
        if codes:
            sql += f" AND code IN ({','.join(['%s'] * len(codes))})"
            params.extend(codes)
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def resolve_ids(row_ids, now_ms):
        """행 id로 해결 처리한다."""
        ids = [int(i) for i in (row_ids or [])]
        if not ids:
            return 0
        conn = database.get_connection('general')
        cursor = conn.cursor()
        changed = 0
        try:
            for i in range(0, len(ids), _CHUNK):
                chunk = ids[i:i + _CHUNK]
                cursor.execute(
                    "UPDATE problem_occurrences SET status = 'resolved', resolved_ms = %s "
                    f"WHERE status = 'open' AND id IN ({','.join(['%s'] * len(chunk))})",
                    [now_ms, *chunk],
                )
                changed += cursor.rowcount or 0
            if changed:
                cursor.execute(_CLEAR_EMPTY_GROUPS_SQL)
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def list_groups():
        """열린 행이 있는 카드 목록 + 음소거 상태."""
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT o.group_key, MIN(o.code) AS code, MIN(o.source) AS source,
                       MIN(o.db_type) AS db_type, MIN(o.library_id) AS library_id,
                       {_SEVERITY_RANK_SQL} AS severity_rank,
                       COUNT(*) AS open_count,
                       MIN(o.first_seen_ms) AS first_seen_ms, MAX(o.last_seen_ms) AS last_seen_ms,
                       MAX(g.muted_ms) AS muted_ms, MAX(g.muted_count) AS muted_count
                FROM problem_occurrences o
                LEFT JOIN problem_groups g ON g.group_key = o.group_key
                WHERE o.status = 'open'
                GROUP BY o.group_key
                ORDER BY severity_rank DESC, last_seen_ms DESC
                """
            )
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_group_series(group_key, limit=50, offset=0):
        """카드 안을 시리즈별로 접어 올린 줄. series_key가 없는 행(카테고리/시스템)은 한 줄씩."""
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(series_key, CONCAT('target:', target_type, ':', target_id)) AS line_key,
                       MAX(series_key) AS series_key, COUNT(*) AS open_count,
                       MIN(target_type) AS target_type, MIN(target_id) AS sample_target_id, MIN(target_path) AS sample_path,
                       MAX(last_seen_ms) AS last_seen_ms
                FROM problem_occurrences
                WHERE status = 'open' AND group_key = %s
                GROUP BY line_key
                ORDER BY open_count DESC, line_key
                LIMIT %s OFFSET %s
                """,
                (group_key, int(limit), int(offset)),
            )
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_group_items(group_key, series_key=None, limit=50, offset=0):
        """카드(또는 그 안 시리즈 한 줄)의 열린 행 목록과 전체 개수."""
        where = "status = 'open' AND group_key = %s"
        params = [group_key]
        if series_key:
            where += " AND series_key = %s"
            params.append(series_key)
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) AS total FROM problem_occurrences WHERE {where}", params)
            total = cursor.fetchone()['total']
            cursor.execute(
                f"SELECT * FROM problem_occurrences WHERE {where} ORDER BY target_path, id LIMIT %s OFFSET %s",
                [*params, int(limit), int(offset)],
            )
            rows = cursor.fetchall()
        return [dict(r) for r in rows], int(total or 0)

    @staticmethod
    def set_group_mute(group_key, muted_count, now_ms):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO problem_groups (group_key, muted_ms, muted_count) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE muted_ms = VALUES(muted_ms), muted_count = VALUES(muted_count)",
                (group_key, now_ms, int(muted_count)),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def clear_group_mute(group_key):
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM problem_groups WHERE group_key = %s", (group_key,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def purge_resolved(before_ms):
        """해결된 지 오래된 행을 지운다. 지운 행 수를 돌려준다."""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM problem_occurrences WHERE status = 'resolved' AND resolved_ms < %s",
                (before_ms,),
            )
            deleted = cursor.rowcount or 0
            cursor.execute(_CLEAR_EMPTY_GROUPS_SQL)
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete_by_library(db_type, library_id):
        """카테고리 삭제/이동 시 그 카테고리의 문제 기록과 카드 상태를 지운다."""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM problem_occurrences WHERE db_type = %s AND library_id = %s",
                (db_type, int(library_id)),
            )
            deleted = cursor.rowcount or 0
            cursor.execute(_CLEAR_EMPTY_GROUPS_SQL)
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---- 출처(source) 단위: 플러그인 문제 카드 계약 (services/plugin_problem_service.py) ----
    @staticmethod
    def count_open_by_source(source):
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS n FROM problem_occurrences WHERE status = 'open' AND source = %s", (source,))
            row = cursor.fetchone()
        return int(row['n'] or 0) if row else 0

    @staticmethod
    def list_oldest_open_ids_by_source(source, limit):
        """출처의 열린 행 중 마지막 발생이 오래된 순으로 id (열린 문제 상한 정리용)."""
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM problem_occurrences WHERE status = 'open' AND source = %s "
                "ORDER BY last_seen_ms, id LIMIT %s",
                (source, int(limit)),
            )
            rows = cursor.fetchall()
        return [int(r['id']) for r in rows]

    @staticmethod
    def resolve_by_source(source, now_ms):
        """출처의 열린 행을 모두 해결 처리한다 (플러그인 비활성화/삭제)."""
        conn = database.get_connection('general')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE problem_occurrences SET status = 'resolved', resolved_ms = %s WHERE status = 'open' AND source = %s",
                (now_ms, source),
            )
            changed = cursor.rowcount or 0
            if changed:
                cursor.execute(_CLEAR_EMPTY_GROUPS_SQL)
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def list_open_sources(prefix):
        """열린 행이 있는 출처 목록 (prefix로 시작하는 것만, 예: 'plugin:')."""
        with database.connection('general') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT source FROM problem_occurrences WHERE status = 'open' AND source LIKE %s",
                (prefix + '%',),
            )
            rows = cursor.fetchall()
        return [r['source'] for r in rows]
