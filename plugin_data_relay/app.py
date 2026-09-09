import os
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from database import (
    init_db, get_db_connection, validate_identifier, validate_field_type,
    InvalidIdentifierError, MAX_FIELDS_PER_PLUGIN, data_table_name,
    get_plugin_fields, register_plugin, verify_plugin_secret,
    get_plugin_status, set_plugin_status,
    register_developer, verify_developer_secret,
    PLUGIN_STATUS_APPROVED, PLUGIN_STATUS_REJECTED,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not app.secret_key or not ADMIN_PASSWORD:
    raise RuntimeError("FLASK_SECRET_KEY and ADMIN_PASSWORD environment variables are required.")


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return response


@app.route('/api/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return '', 200


init_db()


def is_admin_logged_in():
    return session.get("is_admin") is True


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))
        return render_template("login.html", error="비밀번호가 올바르지 않습니다.")
    return render_template("login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/")
@app.route("/admin")
def admin_panel():
    if not is_admin_logged_in():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM plugins ORDER BY created_at DESC")
    plugins_raw = cursor.fetchall()

    plugins = []
    for p in plugins_raw:
        plugin_id = p["plugin_id"]
        fields = get_plugin_fields(cursor, plugin_id)
        cursor.execute("SELECT COUNT(*) AS c FROM plugin_users WHERE plugin_id = ?", (plugin_id,))
        user_count = cursor.fetchone()["c"]
        try:
            cursor.execute(f'SELECT COUNT(*) AS c FROM "{data_table_name(plugin_id)}"')
            record_count = cursor.fetchone()["c"]
        except Exception:
            record_count = 0

        plugins.append({
            "plugin_id": plugin_id,
            "developer_id": p["developer_id"],
            "status": p["status"],
            "created_at": p["created_at"],
            "fields": fields,
            "user_count": user_count,
            "record_count": record_count,
        })

    conn.close()
    return render_template("admin.html", plugins=plugins)


@app.route("/admin/plugins/<plugin_id>/approve", methods=["POST"])
def approve_plugin(plugin_id):
    if not is_admin_logged_in():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    set_plugin_status(cursor, plugin_id, PLUGIN_STATUS_APPROVED)
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))


@app.route("/admin/plugins/<plugin_id>/reject", methods=["POST"])
def reject_plugin(plugin_id):
    if not is_admin_logged_in():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    set_plugin_status(cursor, plugin_id, PLUGIN_STATUS_REJECTED)
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))


def check_plugin_usable(cursor, plugin_id):
    """plugin_id가 존재하고 관리자 승인이 완료됐는지 확인. 문제 있으면 (response, status_code) 튜플 반환, 정상이면 None."""
    status = get_plugin_status(cursor, plugin_id)
    if status is None:
        return jsonify({"success": False, "message": "등록되지 않은 plugin_id입니다."}), 404
    if status != PLUGIN_STATUS_APPROVED:
        return jsonify({"success": False, "message": "관리자 승인 대기 중인 플러그인입니다."}), 403
    return None


def authenticate_end_user(cursor, plugin_id, user_id, secret_token, create_if_missing=False):
    cursor.execute(
        "SELECT * FROM plugin_users WHERE plugin_id = ? AND user_id = ?",
        (plugin_id, user_id),
    )
    user = cursor.fetchone()

    if not user:
        if create_if_missing:
            cursor.execute(
                "INSERT INTO plugin_users (plugin_id, user_id, secret_token) VALUES (?, ?, ?)",
                (plugin_id, user_id, secret_token),
            )
            return True
        return False

    if user["secret_token"] != secret_token:
        if create_if_missing:
            cursor.execute(
                "UPDATE plugin_users SET secret_token = ? WHERE plugin_id = ? AND user_id = ?",
                (secret_token, plugin_id, user_id),
            )
            return True
        return False

    return True


@app.route("/regi_user", methods=["GET", "POST"])
def developer_signup():
    if request.method == "GET":
        return render_template("regi_user.html")

    data = request.get_json(silent=True) or {}
    developer_id = (data.get("developer_id") or "").strip()

    try:
        validate_identifier(developer_id, "developer_id")

        conn = get_db_connection()
        cursor = conn.cursor()
        developer_secret = register_developer(cursor, developer_id)
        conn.commit()
        conn.close()
    except InvalidIdentifierError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    return jsonify({
        "success": True,
        "developer_id": developer_id,
        "developer_secret": developer_secret,
        "message": "개발자 계정이 등록되었습니다. developer_secret은 이 응답에서만 표시되니 반드시 저장하세요.",
    })


@app.route("/register", methods=["GET", "POST"])
def plugin_schema_register():
    if request.method == "GET":
        return render_template("register.html", max_fields=MAX_FIELDS_PER_PLUGIN)

    data = request.get_json(silent=True) or {}
    developer_id = (data.get("developer_id") or "").strip()
    developer_secret = (data.get("developer_secret") or "").strip()
    plugin_id = (data.get("plugin_id") or "").strip()
    raw_fields = data.get("fields") or []

    if not developer_id or not developer_secret:
        return jsonify({"success": False, "message": "developer_id 및 developer_secret이 필요합니다. 먼저 /regi_user에서 개발자 계정을 등록하세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    if not verify_developer_secret(cursor, developer_id, developer_secret):
        conn.close()
        return jsonify({"success": False, "message": "개발자 인증 실패"}), 401

    try:
        validate_identifier(plugin_id, "plugin_id")

        fields = []
        for f in raw_fields:
            name = (f.get("name") or "").strip()
            field_type = (f.get("type") or "").strip().upper()
            validate_identifier(name, "필드명")
            validate_field_type(field_type)
            fields.append({"name": name, "type": field_type})

        plugin_secret = register_plugin(cursor, plugin_id, fields, developer_id)
        conn.commit()
    except InvalidIdentifierError as e:
        conn.close()
        return jsonify({"success": False, "message": str(e)}), 400

    conn.close()
    return jsonify({
        "success": True,
        "plugin_id": plugin_id,
        "plugin_secret": plugin_secret,
        "message": "플러그인이 등록되었습니다. plugin_secret은 이 응답에서만 표시되니 반드시 저장하세요.",
    })


@app.route("/api/<plugin_id>/verify", methods=["POST"])
def verify_end_user(plugin_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    secret_token = data.get("secret_token", "").strip()

    if not user_id or not secret_token:
        return jsonify({"success": False, "message": "user_id 및 secret_token이 필요합니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    usable_error = check_plugin_usable(cursor, plugin_id)
    if usable_error:
        conn.close()
        return usable_error

    auth_ok = authenticate_end_user(cursor, plugin_id, user_id, secret_token, create_if_missing=True)
    conn.commit()
    conn.close()

    if auth_ok:
        return jsonify({"success": True, "message": "인증 및 등록이 완료되었습니다."})
    return jsonify({"success": False, "message": "인증 실패: 잘못된 토큰입니다."}), 401


@app.route("/api/<plugin_id>/records", methods=["POST"])
def add_record(plugin_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    secret_token = data.get("secret_token", "").strip()
    values = data.get("values") or {}

    if not user_id or not secret_token:
        return jsonify({"success": False, "message": "인증 정보가 필요합니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    usable_error = check_plugin_usable(cursor, plugin_id)
    if usable_error:
        conn.close()
        return usable_error

    if not authenticate_end_user(cursor, plugin_id, user_id, secret_token):
        conn.close()
        return jsonify({"success": False, "message": "인증 실패"}), 401

    allowed_fields = {f["field_name"]: f["field_type"] for f in get_plugin_fields(cursor, plugin_id)}
    unknown = set(values.keys()) - set(allowed_fields.keys())
    if unknown:
        conn.close()
        return jsonify({"success": False, "message": f"등록되지 않은 필드입니다: {sorted(unknown)}"}), 400

    columns = ["user_id"] + list(values.keys())
    placeholders = ["?"] * len(columns)
    params = [user_id] + [values[k] for k in values.keys()]

    quoted_columns = ", ".join(f'"{c}"' if c != "user_id" else c for c in columns)
    table_name = data_table_name(plugin_id)
    cursor.execute(
        f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({", ".join(placeholders)})',
        params,
    )
    record_id = cursor.lastrowid
    conn.commit()

    cursor.execute(f'SELECT * FROM "{table_name}" WHERE id = ?', (record_id,))
    new_record = dict(cursor.fetchone())
    conn.close()

    return jsonify({"success": True, "record": new_record})


@app.route("/api/<plugin_id>/records", methods=["GET"])
def list_records(plugin_id):
    user_id = request.args.get("user_id", "").strip()
    secret_token = request.args.get("secret_token", "").strip()
    order_by = request.args.get("order_by", "").strip()
    order_dir = request.args.get("order_dir", "desc").strip().lower()
    limit = request.args.get("limit", "50").strip()

    if not user_id or not secret_token:
        return jsonify({"success": False, "message": "인증 정보가 필요합니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    usable_error = check_plugin_usable(cursor, plugin_id)
    if usable_error:
        conn.close()
        return usable_error

    if not authenticate_end_user(cursor, plugin_id, user_id, secret_token):
        conn.close()
        return jsonify({"success": False, "message": "인증 실패"}), 401

    allowed_fields = {f["field_name"] for f in get_plugin_fields(cursor, plugin_id)}
    fixed_sort_fields = {"id", "created_at"}

    if order_by and order_by not in allowed_fields and order_by not in fixed_sort_fields:
        conn.close()
        return jsonify({"success": False, "message": f"정렬할 수 없는 필드입니다: {order_by}"}), 400

    if order_dir not in ("asc", "desc"):
        order_dir = "desc"

    try:
        limit = max(1, min(int(limit), 200))
    except ValueError:
        limit = 50

    table_name = data_table_name(plugin_id)
    order_clause = f'ORDER BY "{order_by}" {order_dir.upper()}' if order_by else "ORDER BY id DESC"
    cursor.execute(f'SELECT * FROM "{table_name}" {order_clause} LIMIT ?', (limit,))
    records = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({"success": True, "records": records})


@app.route("/api/<plugin_id>/records/<int:record_id>", methods=["DELETE"])
def delete_record(plugin_id, record_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", request.args.get("user_id", "")).strip()
    secret_token = data.get("secret_token", request.args.get("secret_token", "")).strip()

    if not user_id or not secret_token:
        return jsonify({"success": False, "message": "인증 정보가 필요합니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    usable_error = check_plugin_usable(cursor, plugin_id)
    if usable_error:
        conn.close()
        return usable_error

    if not authenticate_end_user(cursor, plugin_id, user_id, secret_token):
        conn.close()
        return jsonify({"success": False, "message": "인증 실패"}), 401

    table_name = data_table_name(plugin_id)
    cursor.execute(f'SELECT * FROM "{table_name}" WHERE id = ?', (record_id,))
    record = cursor.fetchone()

    if not record:
        conn.close()
        return jsonify({"success": False, "message": "해당 레코드를 찾을 수 없습니다."}), 404

    if record["user_id"] != user_id:
        conn.close()
        return jsonify({"success": False, "message": "삭제 권한이 없습니다."}), 403

    cursor.execute(f'DELETE FROM "{table_name}" WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "레코드가 삭제되었습니다."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
