# -*- coding: utf-8 -*-
"""
db_retry.py – DB 잠금(일시적 경합) 판별과 재시도 공용 헬퍼.

예전엔 tools/scanner/engine.py에만 있었고, 커밋 재시도가 잠금 오류 때 rollback()부터 한 뒤 다시
commit()해서 쓰기를 통째로 버렸다(SQLite는 COMMIT이 잠금으로 실패해도 트랜잭션이 열린 채 남는다 -
롤백하면 빈 트랜잭션이 '성공'으로 커밋된다). 여기서는 두 경우를 나눈다.

- commit_with_retry: 이미 execute가 끝난 트랜잭션의 COMMIT만 잠금으로 실패한 경우 → 롤백 없이 COMMIT 재시도.
- run_write_with_retry: execute 단계에서 잠금이 나거나(SQLite의 일반적 경우) MariaDB 데드락처럼
  서버가 트랜잭션을 되돌린 경우 → 롤백 후 작업(work) 전체를 다시 실행. work는 멱등이어야 한다.
"""
import sqlite3
import time


def is_db_locked_error(exc):
    """SQLite 'database is locked'와 MariaDB lock-wait-timeout(1205)/deadlock(1213)을 일시적 경합으로 본다."""
    try:
        if isinstance(exc, sqlite3.OperationalError) and 'locked' in str(exc).lower():
            return True
        msg = str(exc).lower()
        if 'lock wait timeout' in msg or 'deadlock' in msg or 'try restarting transaction' in msg:
            return True
        try:
            import pymysql
            if isinstance(exc, pymysql.err.OperationalError):
                code = exc.args[0] if exc.args else None
                return code in (1205, 1213) or 'lock' in msg
        except ImportError:
            pass
        return False
    except Exception:
        return False


def _backoff(attempt, cap=3.0):
    return min(cap, 0.2 * (2 ** (attempt - 1)))


def _safe_rollback(conn):
    try:
        conn.rollback()
    except Exception:
        pass


def commit_with_retry(conn, context_label, max_attempts=12, sleep=time.sleep):
    """COMMIT이 잠금으로 실패하면 트랜잭션을 그대로 둔 채 COMMIT만 다시 시도한다.
    끝내 실패하면 그때 롤백하고 마지막 예외를 올린다. 잠금이 아닌 예외는 바로 올린다."""
    for attempt in range(1, max_attempts + 1):
        try:
            conn.commit()
            return True
        except Exception as e:
            if not is_db_locked_error(e):
                raise
            if attempt >= max_attempts:
                _safe_rollback(conn)
                raise
            wait_sec = _backoff(attempt)
            print(f"[DB-Retry] {context_label} commit locked (attempt {attempt}/{max_attempts}). Retrying in {wait_sec:.2f}s...")
            sleep(wait_sec)
    return False


def run_write_with_retry(conn, work, context_label, max_attempts=5, sleep=time.sleep):
    """work(conn)으로 쓰기를 실행하고 커밋한다. 잠금 오류면 롤백 후 work를 처음부터 다시 실행한다.
    work는 다시 실행해도 결과가 같아야 한다(UPDATE, DELETE 후 INSERT 등). work의 반환값을 돌려준다.
    끝내 실패하거나 잠금이 아닌 예외면 롤백하고 예외를 올린다 - 반쯤 쓴 트랜잭션을 남기지 않는다."""
    for attempt in range(1, max_attempts + 1):
        try:
            result = work(conn)
            conn.commit()
            return result
        except Exception as e:
            _safe_rollback(conn)
            if not is_db_locked_error(e) or attempt >= max_attempts:
                raise
            wait_sec = _backoff(attempt)
            print(f"[DB-Retry] {context_label} write locked (attempt {attempt}/{max_attempts}). Retrying in {wait_sec:.2f}s...")
            sleep(wait_sec)
    return None
