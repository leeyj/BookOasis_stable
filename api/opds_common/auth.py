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

    user = get_basic_auth_user(username)
    if not user:
        return None
    if not check_password_hash(user['password_hash'], password):
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
