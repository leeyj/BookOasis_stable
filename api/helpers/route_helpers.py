# -*- coding: utf-8 -*-
"""
route_helpers.py – 라우트에서 반복되던 응답/세션 처리 공용 헬퍼.

- error_response: `except Exception as e: return jsonify({'success': False, 'error': str(e)}), 500`가
  21개 파일 약 150곳에 있었고 대부분 로그 없이 예외를 삼켰다. 응답 형태·문구는 그대로 두고
  서버 로그에 [API-ERROR] 한 줄을 남긴다(쓰기 요청 실패만 남기던 [API-FAIL]과 달리 GET도 포함).
- current_user_id: 예전 session.get('user_id', 1)은 세션이 비면 관리자(1번)로 처리했다.
"""
from flask import jsonify, request, session


def error_response(exc, status=500):
    """예외를 서버 로그에 남기고 JSON 오류 응답을 돌려준다.

    응답에 예외 원문을 그대로 싣지 않는다: DB 오류 문구에는 DB 계정·호스트·DB 이름이, 파일 오류에는
    서버 경로가 들어 있다(2026-11 보안 점검, .21에서 `?type=evil` 하나로 MariaDB 계정이 응답에 나옴).
    - 잘못된 db_type → 400 + 일반 문구
    - ValueError → 원문 유지. 서비스가 사용자에게 보여 줄 문구를 담아 던지는 관례(약 160곳)라서.
    - 그 밖 → 일반 문구. 원문은 아래 [API-ERROR] 로그에만 남는다."""
    from database import InvalidDbTypeError
    from utils.i18n import _t
    if isinstance(exc, InvalidDbTypeError):
        status = 400
    try:
        method = request.method
        path = request.path
    except RuntimeError:  # 요청 컨텍스트 밖(직접 호출 테스트 등)
        method, path = '-', '-'
    print(f"[API-ERROR] {method} {path} -> {status}: {type(exc).__name__}: {exc}")
    if isinstance(exc, InvalidDbTypeError):
        message = _t('api.err_invalid_db_type')
    elif isinstance(exc, ValueError):
        message = str(exc)
    else:
        message = _t('api.err_internal')
    return jsonify({'success': False, 'error': message}), status


def current_user_id():
    """로그인한 사용자 ID. 세션이 없으면 None (기본값 1로 관리자 취급하지 않는다)."""
    return session.get('user_id')


def session_user_info():
    """(user_id, role) - annotation/bookmark/collection/plugin 라우트가 따로 갖던 사본을 대체."""
    return session.get('user_id'), session.get('role')


def db_type_arg(allowed, default='general', param='db_type'):
    """쿼리 파라미터의 db_type을 허용 목록으로 걸러 돌려준다. 목록 밖이면 default."""
    raw_type = request.args.get(param, default)
    return raw_type if raw_type in allowed else default
