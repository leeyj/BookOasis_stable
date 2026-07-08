# -*- coding: utf-8 -*-
"""Shared auth helpers for OPDS and App OPDS endpoints."""

from flask import Response
import database
from werkzeug.security import check_password_hash


def verify_basic_auth_credentials(username: str, password: str, require_admin: bool = False) -> bool:
    if not username or not password:
        return False

    conn = database.get_connection('general')
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password_hash, role FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return False
    if not check_password_hash(row['password_hash'], password):
        return False
    if require_admin and row['role'] != 'admin':
        return False
    return True


def unauthorized_response(realm: str) -> Response:
    return Response(
        "Unauthorized",
        status=401,
        headers={'WWW-Authenticate': f'Basic realm="{realm}"'}
    )
