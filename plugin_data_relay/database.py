import sqlite3
import os
import re
import secrets
import hashlib

DB_PATH = os.environ.get("RELAY_DB_PATH", os.path.join(os.path.dirname(__file__), "plugin_relay.db"))

SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,30}$")
ALLOWED_FIELD_TYPES = {"TEXT", "INTEGER", "REAL"}
MAX_FIELDS_PER_PLUGIN = 5

# 동적 테이블에 항상 존재하는 고정 컬럼 — 커스텀 필드명으로 재사용 불가
FIXED_COLUMN_NAMES = {"id", "user_id", "created_at"}

PLUGIN_STATUS_PENDING = "pending"
PLUGIN_STATUS_APPROVED = "approved"
PLUGIN_STATUS_REJECTED = "rejected"
PLUGIN_STATUSES = {PLUGIN_STATUS_PENDING, PLUGIN_STATUS_APPROVED, PLUGIN_STATUS_REJECTED}

# sqlite/SQL 예약어 중 식별자로 쓰이면 위험한 것들 차단
RESERVED_WORDS = {
    "select", "insert", "update", "delete", "drop", "create", "alter", "table",
    "from", "where", "join", "union", "exec", "execute", "pragma", "attach",
    "detach", "database", "index", "trigger", "view", "transaction", "commit",
    "rollback", "into", "values", "set", "and", "or", "not", "null", "primary",
    "key", "foreign", "references", "default", "check", "constraint",
}


class InvalidIdentifierError(ValueError):
    pass


def validate_identifier(name, label="식별자"):
    if not name or not SAFE_IDENTIFIER_RE.match(name):
        raise InvalidIdentifierError(
            f"{label}은(는) 영문/숫자/밑줄(_)로만 이루어진 31자 이내 문자열이어야 하며, 숫자로 시작할 수 없습니다."
        )
    if name.lower() in RESERVED_WORDS:
        raise InvalidIdentifierError(f"{label}에 예약어({name})는 사용할 수 없습니다.")
    return name


def validate_field_type(field_type):
    if field_type not in ALLOWED_FIELD_TYPES:
        raise InvalidIdentifierError(f"필드 타입은 {sorted(ALLOWED_FIELD_TYPES)} 중 하나여야 합니다.")
    return field_type


def data_table_name(plugin_id):
    # plugin_id는 항상 validate_identifier()를 통과한 값만 여기 들어와야 함
    return f"plugin_data_{plugin_id}"


def hash_secret(secret_value):
    return hashlib.sha256(secret_value.encode("utf-8")).hexdigest()


def generate_secret():
    return secrets.token_hex(16)  # 32자리 hex


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS developers (
            developer_id TEXT PRIMARY KEY,
            developer_secret_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plugins (
            plugin_id TEXT PRIMARY KEY,
            plugin_secret_hash TEXT NOT NULL,
            developer_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 기존(승인/개발자 계정 개념 도입 이전)에 생성된 DB를 위한 마이그레이션
    for column_def in ("status TEXT NOT NULL DEFAULT 'pending'", "developer_id TEXT NOT NULL DEFAULT ''"):
        try:
            cursor.execute(f"ALTER TABLE plugins ADD COLUMN {column_def}")
        except sqlite3.OperationalError:
            pass  # 컬럼이 이미 존재함

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plugin_fields (
            plugin_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            field_type TEXT NOT NULL,
            field_order INTEGER NOT NULL,
            PRIMARY KEY (plugin_id, field_name),
            FOREIGN KEY (plugin_id) REFERENCES plugins (plugin_id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plugin_users (
            plugin_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            secret_token TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (plugin_id, user_id),
            FOREIGN KEY (plugin_id) REFERENCES plugins (plugin_id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()


def get_plugin_fields(cursor, plugin_id):
    """등록된 필드 목록을 field_order 순으로 반환. 없으면 빈 리스트."""
    cursor.execute(
        "SELECT field_name, field_type FROM plugin_fields WHERE plugin_id = ? ORDER BY field_order",
        (plugin_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def register_developer(cursor, developer_id):
    """
    developer_id: 검증된 문자열
    반환: developer_secret (평문, 이 호출에서만 노출)
    """
    cursor.execute("SELECT developer_id FROM developers WHERE developer_id = ?", (developer_id,))
    if cursor.fetchone():
        raise InvalidIdentifierError(f"developer_id '{developer_id}'는 이미 등록되어 있습니다.")

    developer_secret = generate_secret()
    cursor.execute(
        "INSERT INTO developers (developer_id, developer_secret_hash) VALUES (?, ?)",
        (developer_id, hash_secret(developer_secret)),
    )
    return developer_secret


def verify_developer_secret(cursor, developer_id, developer_secret):
    cursor.execute("SELECT developer_secret_hash FROM developers WHERE developer_id = ?", (developer_id,))
    row = cursor.fetchone()
    if not row:
        return False
    return row["developer_secret_hash"] == hash_secret(developer_secret)


def register_plugin(cursor, plugin_id, fields, developer_id):
    """
    plugin_id: 검증된 문자열
    fields: [{"name": str, "type": str}, ...] (1~5개, 이미 검증된 값)
    developer_id: 이미 /regi_user로 등록 및 인증된 개발자 식별자
    반환: plugin_secret (평문, 이 호출에서만 노출)
    """
    if not fields or len(fields) > MAX_FIELDS_PER_PLUGIN:
        raise InvalidIdentifierError(f"필드는 1개 이상 {MAX_FIELDS_PER_PLUGIN}개 이하여야 합니다.")

    cursor.execute("SELECT plugin_id FROM plugins WHERE plugin_id = ?", (plugin_id,))
    if cursor.fetchone():
        raise InvalidIdentifierError(f"plugin_id '{plugin_id}'는 이미 등록되어 있습니다.")

    seen_names = set()
    for f in fields:
        if f["name"] in FIXED_COLUMN_NAMES:
            raise InvalidIdentifierError(f"필드명 '{f['name']}'은(는) 고정 컬럼명이라 사용할 수 없습니다.")
        if f["name"] in seen_names:
            raise InvalidIdentifierError(f"필드명 '{f['name']}'이(가) 중복되었습니다.")
        seen_names.add(f["name"])

    plugin_secret = generate_secret()
    cursor.execute(
        "INSERT INTO plugins (plugin_id, plugin_secret_hash, developer_id) VALUES (?, ?, ?)",
        (plugin_id, hash_secret(plugin_secret), developer_id),
    )

    for order, f in enumerate(fields):
        cursor.execute(
            "INSERT INTO plugin_fields (plugin_id, field_name, field_type, field_order) VALUES (?, ?, ?, ?)",
            (plugin_id, f["name"], f["type"], order),
        )

    table_name = data_table_name(plugin_id)
    custom_columns_sql = ", ".join(f'"{f["name"]}" {f["type"]}' for f in fields)
    # 식별자(table_name, field name/type)는 모두 위에서 검증된 값만 사용 — 값은 바인드 파라미터 불가 영역이므로
    # 여기서 조합하는 것 외 방법이 없다.
    cursor.execute(f'''
        CREATE TABLE "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            {custom_columns_sql}
        )
    ''')

    return plugin_secret


def verify_plugin_secret(cursor, plugin_id, plugin_secret):
    cursor.execute("SELECT plugin_secret_hash FROM plugins WHERE plugin_id = ?", (plugin_id,))
    row = cursor.fetchone()
    if not row:
        return False
    return row["plugin_secret_hash"] == hash_secret(plugin_secret)


def plugin_exists(cursor, plugin_id):
    cursor.execute("SELECT 1 FROM plugins WHERE plugin_id = ?", (plugin_id,))
    return cursor.fetchone() is not None


def get_plugin_status(cursor, plugin_id):
    cursor.execute("SELECT status FROM plugins WHERE plugin_id = ?", (plugin_id,))
    row = cursor.fetchone()
    return row["status"] if row else None


def set_plugin_status(cursor, plugin_id, status):
    if status not in PLUGIN_STATUSES:
        raise InvalidIdentifierError(f"status는 {sorted(PLUGIN_STATUSES)} 중 하나여야 합니다.")
    cursor.execute("UPDATE plugins SET status = ? WHERE plugin_id = ?", (status, plugin_id))
    return cursor.rowcount > 0


if __name__ == "__main__":
    init_db()
    print("Plugin relay database initialized successfully.")
