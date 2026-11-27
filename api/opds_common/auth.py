# -*- coding: utf-8 -*-
"""Shared auth helpers for OPDS and App OPDS endpoints."""

from flask import Response
import database
from werkzeug.security import check_password_hash


def get_basic_auth_user(username: str):
    if not username:
        return None

    from repositories.user_repository import UserRepository
    return UserRepository.find_by_username('general', username)


def authenticate_basic_auth_user(username: str, password: str, require_admin: bool = False):
    if not username or not password:
        return None

    from flask import has_request_context
    from utils import auth_throttle
    in_request = has_request_context()
    if in_request:
        auth_throttle.abort_if_blocked('basic')  # 429 before the password is even checked

    user = get_basic_auth_user(username)
    ok = bool(user) and check_password_hash(user['password_hash'], password)
    if in_request:
        auth_throttle.note_result(ok, 'basic')
    if not ok:
        return None
    if require_admin and user['role'] != 'admin':
        return None
    return user


def verify_basic_auth_credentials(username: str, password: str, require_admin: bool = False) -> bool:
    return authenticate_basic_auth_user(username, password, require_admin=require_admin) is not None


def unauthorized_response(realm: str) -> Response:
    return Response(
        "Unauthorized",
        status=401,
        headers={'WWW-Authenticate': f'Basic realm="{realm}"'}
    )
