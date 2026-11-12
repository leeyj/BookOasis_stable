# -*- coding: utf-8 -*-
"""
mcp_admin_tools_service.py – MCP 서버(tools/mcp_server.py)용 범용 읽기전용 SQL 쿼리,
서버 로그 조회, 기존 GET REST API 프록시, 그리고 저위험(Tier A) write 도구. 진단 항목마다
전용 리포지토리/서비스 메서드를 새로 만들어야 했던 library_diagnostics_service.py의 한계를
보완한다 - Claude가 스키마나 API 경로만 알면 즉석에서 직접 조회할 수 있다.

write 도구 설계 원칙(docs/guide_mcp_server.md 참고):
- 코어/플러그인 소스 파일은 절대 건드리지 않는다 - DB만, 그것도 이미 검증된 서비스/리포지토리
  메서드를 통해서만 쓴다. run_readonly_query와 대칭되는 범용 write SQL 도구는 절대 만들지 않는다.
- MCP_WRITE_ENABLED 설정(기본 꺼짐)이 켜져 있어야만 Tier A write 도구가 동작한다
  (_require_write_enabled 참고) - 관리자가 설정 탭에서 명시적으로 켜야 하는 킬스위치.
- 모든 write 실행은 logs/mcp_write_audit.log에 무엇을 바꿨는지(대상/변경 전후 값) 기록한다.
- 대량/파괴적 작업(Tier B)은 여기서 다루지 않는다 - services/mcp_proposal_service.py의
  "제안→관리자 승인" 큐를 통한다. `_validate_metadata_fields`/`_apply_book_metadata`는 그
  큐가 재사용하는 공유 헬퍼이므로 시그니처를 바꿀 때 mcp_proposal_service.py도 확인할 것.
"""
import os
import re
import json
from datetime import datetime
from collections import deque

from services import series_metadata_patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
MCP_WRITE_AUDIT_LOG = os.path.join(LOGS_DIR, 'mcp_write_audit.log')

_VALID_DB_TYPES = ('general', 'adult', 'audiobook', 'video')

_ALLOWED_LEADING_KEYWORDS = ('select', 'with', 'explain', 'pragma', 'show', 'describe')
# SHOW/DESCRIBE는 MariaDB용 스키마 조회(SHOW COLUMNS/INDEX/CREATE TABLE 등) - 본질적으로 읽기 전용이라
# 'SHOW CREATE TABLE'이 금지 키워드(create)에 걸리지 않도록 금지어 검사를 건너뛴다.
_SCHEMA_INSPECTION_KEYWORDS = ('show', 'describe')
_BANNED_KEYWORDS = (
    'insert', 'update', 'delete', 'drop', 'alter', 'create', 'attach', 'detach',
    'replace', 'truncate', 'grant', 'revoke', 'vacuum',
)
# PRAGMA는 시작 키워드로는 허용한다(table_info/index_list 등 스키마 조회에 필요) - 값을
# 바꾸는 PRAGMA(journal_mode=DELETE 등)가 섞여 들어와도 sqlite는 읽기전용(mode=ro)
# 커넥션, MariaDB는 SESSION READ ONLY 세션에서 실행되므로 DB 레벨에서 실제로 막힌다.

_ALLOWED_LOG_FILES = ('media_server.log', 'scanner.log', 'lazy_scanner.log', 'scan_history.log', 'mcp_write_audit.log')


def _validate_readonly_sql(sql):
    """SELECT/WITH/EXPLAIN 단일 구문만 허용 (앱 레벨 1차 방어 - DB 레벨 방어가 진짜 안전판)"""
    stripped = (sql or '').strip().rstrip(';').strip()
    if not stripped:
        raise ValueError('sql이 비어있습니다.')
    if ';' in stripped:
        raise ValueError('세미콜론으로 구분된 다중 쿼리는 허용되지 않습니다.')

    first_word = stripped.split(None, 1)[0].lower()
    if first_word not in _ALLOWED_LEADING_KEYWORDS:
        raise ValueError(f"SELECT/WITH/EXPLAIN 쿼리만 허용됩니다 (시작 키워드: {first_word})")

    if first_word in _SCHEMA_INSPECTION_KEYWORDS:
        return stripped

    lowered = stripped.lower()
    for kw in _BANNED_KEYWORDS:
        if re.search(rf'\b{kw}\b', lowered):
            raise ValueError(f'허용되지 않는 키워드가 포함되어 있습니다: {kw}')

    return stripped


def _validate_db_type(db_type):
    db_type = (db_type or 'general').strip().lower()
    if db_type not in _VALID_DB_TYPES:
        raise ValueError(f"지원하지 않는 db_type입니다: {db_type} (허용값: {', '.join(_VALID_DB_TYPES)})")
    return db_type


class McpAdminToolsService:
    @staticmethod
    def get_version_info():
        """VERSION 파일(루트)의 컴포넌트별 버전을 그대로 읽어 반환한다 (네트워크 호출 없음)."""
        version_path = os.path.join(BASE_DIR, 'VERSION')
        info = {}
        with open(version_path, 'r', encoding='utf-8') as f:
            for line in f:
                key, sep, value = line.strip().partition(':')
                if sep:
                    info[key.strip().strip('"')] = value.strip().strip('"')
        return {'dashboard': info.get('dashboard'), 'state': info.get('state'), 'components': info}

    @staticmethod
    def run_readonly_query(db_type, sql, max_rows=200):
        db_type = _validate_db_type(db_type)
        sql = _validate_readonly_sql(sql)
        max_rows = max(1, min(int(max_rows or 200), 1000))

        import database
        if database.is_mariadb_mode():
            rows, columns = McpAdminToolsService._run_mariadb_readonly(db_type, sql, max_rows)
        else:
            rows, columns = McpAdminToolsService._run_sqlite_readonly(db_type, sql, max_rows)

        truncated = len(rows) > max_rows
        return {
            'db_type': db_type,
            'columns': columns,
            'rows': rows[:max_rows],
            'row_count': min(len(rows), max_rows),
            'truncated': truncated,
        }

    @staticmethod
    def _run_sqlite_readonly(db_type, sql, max_rows):
        """전용 read-only URI 커넥션 - 풀을 쓰지 않고, OS 레벨에서 물리적으로 쓰기가
        불가능한 별도 연결을 매번 새로 열고 닫는다 (진짜 안전판)."""
        import sqlite3
        import database
        db_path = database.get_db_path(db_type)
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout = {database.SQLITE_BUSY_TIMEOUT_MS}")
            cursor = conn.execute(sql)
            fetched = cursor.fetchmany(max_rows + 1)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = [dict(row) for row in fetched]
            return rows, columns
        finally:
            conn.close()

    @staticmethod
    def _run_mariadb_readonly(db_type, sql, max_rows):
        """풀 커넥션을 빌리되 세션을 READ ONLY로 걸었다가 반드시 READ WRITE로 원복 후
        반납한다 - 세션 상태이므로 그대로 반납하면 다음 사용자가 쓰기를 못 하게 되는
        사고가 나기 때문."""
        import database
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute(sql)
            fetched = cursor.fetchmany(max_rows + 1)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = [dict(row) for row in fetched]
            return rows, columns
        finally:
            try:
                cursor.execute("SET SESSION TRANSACTION READ WRITE")
            except Exception:
                pass
            conn.close()

    @staticmethod
    def read_log_file(log_name, lines=200, search=None):
        if log_name not in _ALLOWED_LOG_FILES:
            raise ValueError(f"허용되지 않는 로그 파일입니다. 허용 목록: {', '.join(_ALLOWED_LOG_FILES)}")

        lines = max(1, min(int(lines or 200), 1000))
        log_path = os.path.join(LOGS_DIR, log_name)
        if not os.path.exists(log_path):
            return {'exists': False, 'file': log_name, 'lines': []}

        search_lower = (search or '').strip().lower()
        matched = deque(maxlen=lines)
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if search_lower and search_lower not in line.lower():
                    continue
                matched.append(line.rstrip('\n'))

        return {
            'exists': True,
            'file': log_name,
            'returned_lines': len(matched),
            'lines': list(matched),
        }

    @staticmethod
    def call_api(path, query_params=None, max_response_chars=20000):
        """기존 GET REST API(docs/api_endpoints.md)를 그대로 호출한다. GET 외의
        메서드는 이 함수 자체가 호출할 방법을 제공하지 않는다(구조적 안전장치 -
        run_readonly_query가 SELECT만 허용하는 것과 동급)."""
        path = (path or '').strip()
        if not path.startswith('/api/'):
            raise ValueError("path는 '/api/'로 시작하는 API 경로여야 합니다.")

        max_response_chars = max(500, min(int(max_response_chars or 20000), 200000))

        client = _get_api_client()
        resp = client.get(path, query_string=query_params or {})

        content_type = resp.content_type or ''
        if 'application/json' in content_type:
            try:
                body = resp.get_json(silent=True)
            except Exception:
                body = None
            body_text = json.dumps(body, ensure_ascii=False) if body is not None else (resp.get_data(as_text=True) or '')
        else:
            body = None
            body_text = resp.get_data(as_text=True) or ''

        truncated = len(body_text) > max_response_chars
        if truncated:
            body_text = body_text[:max_response_chars]
            body = None  # 잘렸으면 파싱된 JSON이 아니라 잘린 원문 텍스트로 반환

        return {
            'status_code': resp.status_code,
            'content_type': content_type,
            'body': body if (body is not None and not truncated) else body_text,
            'truncated': truncated,
        }

    # ------------------------------------------------------------------
    # Tier A write 도구 - 이미 검증된 서비스/리포지토리 메서드만 호출한다.
    # ------------------------------------------------------------------

    @staticmethod
    def update_book_metadata(db_type, series_name, library_id='all', **fields):
        """시리즈 장르/태그/작가 등 메타데이터를 부분 수정한다 (Tier A, 즉시 실행).
        전달하지 않은 필드는 현재 값을 그대로 유지한다(부분 업데이트)."""
        McpAdminToolsService._require_write_enabled()
        db_type = _validate_db_type(db_type)
        series_name = (series_name or '').strip()
        if not series_name:
            raise ValueError('series_name이 비어있습니다.')

        McpAdminToolsService._validate_metadata_fields(fields)
        changed, success, message = McpAdminToolsService._apply_book_metadata(db_type, series_name, library_id, fields)

        McpAdminToolsService._write_audit_log('update_book_metadata', db_type, series_name, changed)

        return {'success': bool(success), 'message': message, 'series_name': series_name, 'changed_fields': changed}

    # 필드 검증·병합 저장은 관리자 테이블 뷰 셀 편집과 같이 쓰도록 services/series_metadata_patch.py로 옮겼다.
    METADATA_ALLOWED_FIELDS = series_metadata_patch.ALLOWED_FIELDS

    @staticmethod
    def _validate_metadata_fields(fields):
        """update_book_metadata(Tier A)와 Tier B 제안/승인 양쪽이 공유하는 필드 검증.
        Tier B는 제안 생성 시점과 승인 시점 양쪽에서 이 검증을 다시 돌려, 제안이 오래 대기하는 동안
        검증 로직이 바뀌어도 승인 시점 기준으로 재확인한다."""
        series_metadata_patch.validate_fields(fields)

    @staticmethod
    def _apply_book_metadata(db_type, series_name, library_id, fields):
        """시리즈 하나에 값을 병합·적용한다. Returns: (changed_fields dict, success bool, message str)"""
        return series_metadata_patch.apply_fields(db_type, series_name, library_id, fields)

    @staticmethod
    def bulk_set_favorite(db_type, book_ids, is_favorite, user_id):
        """도서 id 목록에 대한 즐겨찾기 일괄 등록/해제. 이미 UI(작가별 모음 카드)가 쓰는
        BookRepository.update_favorites_bulk()를 그대로 위임한다."""
        McpAdminToolsService._require_write_enabled()
        db_type = _validate_db_type(db_type)
        if not isinstance(book_ids, list) or not book_ids:
            raise ValueError('book_ids는 비어있지 않은 리스트여야 합니다.')
        if len(book_ids) > 500:
            raise ValueError('한 번에 최대 500건까지만 처리할 수 있습니다. 더 큰 배치는 propose_bulk_set_favorite로 제안을 만들어 관리자 승인을 받으세요.')

        book_ids = [int(b) for b in book_ids]
        from repositories.book_repository import BookRepository
        BookRepository.update_favorites_bulk(db_type, book_ids, is_favorite, user_id)

        McpAdminToolsService._write_audit_log(
            'bulk_set_favorite', db_type, f"{len(book_ids)} book(s)",
            {'is_favorite': {'before': None, 'after': bool(int(is_favorite))}, 'book_ids': book_ids, 'user_id': user_id},
        )
        return {'success': True, 'affected_count': len(book_ids), 'is_favorite': bool(int(is_favorite))}

    @staticmethod
    def _require_write_enabled():
        from services.settings_service import SettingsService
        enabled = SettingsService.get('MCP_WRITE_ENABLED', '0')
        if str(enabled) != '1':
            raise ValueError(
                'MCP 쓰기 도구가 비활성화되어 있습니다. 관리자가 설정 > 일반 설정에서 '
                '"MCP 쓰기 도구 허용"을 켜야 사용할 수 있습니다.'
            )

    @staticmethod
    def _write_audit_log(tool_name, db_type, target, changed):
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            entry = {
                'timestamp': datetime.now().isoformat(timespec='seconds'),
                'tool': tool_name,
                'db_type': db_type,
                'target': target,
                'changed': changed,
            }
            with open(MCP_WRITE_AUDIT_LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[McpAdminToolsService] Failed to write the write-audit log: {e}")


_api_app = None
_api_client = None


def _get_api_client():
    """MCP 프로세스 안에서만 쓰는 별도의 가벼운 Flask 앱 + test_client 싱글턴.
    core.py를 그대로 임포트하면 DB 마이그레이션/스케줄러/스캐너 워커 프로세스까지
    다시 기동시켜버려서(core.py의 모듈 최상단 부작용) 이미 떠 있는 웹 프로세스와
    충돌한다 - 대신 라우트/인증 로직이 전부 들어있는 api_bp만 별도 앱에 등록해서
    재사용한다. 관리자 세션은 test_client의 세션 트랜잭션으로 직접 주입한다(실제
    로그인 없이 in-process 호출이라 안전 - 네트워크를 타지 않으므로 SECRET_KEY가
    실제 운영 프로세스와 같을 필요도 없다)."""
    global _api_app, _api_client
    if _api_client is not None:
        return _api_client

    from flask import Flask
    from api import api_bp
    from repositories.user_repository import UserRepository

    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY') or 'mcp-internal-ephemeral-key'
    app.register_blueprint(api_bp)
    client = app.test_client()

    admin = next((u for u in UserRepository.get_all_users('general') if u.get('role') == 'admin'), None)
    if not admin:
        raise RuntimeError('관리자 계정이 없어 call_api 툴을 쓸 수 없습니다.')

    with client.session_transaction() as sess:
        sess['user_id'] = admin['id']
        sess['username'] = admin['username']
        sess['role'] = 'admin'
        sess['is_default_password'] = admin.get('is_default_password', 0)

    _api_app, _api_client = app, client
    return client
