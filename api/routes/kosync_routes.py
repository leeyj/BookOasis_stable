# -*- coding: utf-8 -*-
"""
kosync_routes.py – KOReader 진행 동기화 (kosync 호환 API) + 계정별 동기화 비밀번호 설정

KOReader: 설정 → 진행 상황 동기화 → 사용자 지정 동기화 서버 = http(s)://<서버>/kosync
  GET  /kosync/users/auth                 (x-auth-user, x-auth-key = 동기화 비밀번호의 MD5)
  PUT  /kosync/syncs/progress             {document, progress, percentage, device, device_id}
  GET  /kosync/syncs/progress/<document>
  POST /kosync/users/create               - BookOasis 계정을 쓰므로 가입은 받지 않는다
/kosync는 세션 로그인 검사에서 빠져 있고(api/auth.py) 위 헤더로 직접 인증한다.

웹(로그인 세션): GET/POST/DELETE /api/kosync/settings - 동기화 비밀번호 설정 상태/설정/해제
"""
from flask import Blueprint, jsonify, request, session

from services import kosync_service

kosync_bp = Blueprint('kosync', __name__)

_JSON = 'application/vnd.koreader.v1+json'


def _reply(body, status=200):
    res = jsonify(body)
    res.status_code = status
    return res


def _kosync_user():
    return kosync_service.authenticate(request.headers.get('x-auth-user'), request.headers.get('x-auth-key'))


@kosync_bp.route('/kosync/users/create', methods=['POST'])
def kosync_register():
    return _reply({'message': 'BookOasis 계정을 사용합니다. 웹의 계정 메뉴 → KOReader 동기화에서 동기화 비밀번호를 정한 뒤 로그인하세요.'}, 402)


@kosync_bp.route('/kosync/users/auth', methods=['GET'])
def kosync_auth():
    if not _kosync_user():
        return _reply({'message': 'Unauthorized'}, 401)
    return _reply({'authorized': 'OK'})


@kosync_bp.route('/kosync/syncs/progress', methods=['PUT'])
def kosync_push():
    user = _kosync_user()
    if not user:
        return _reply({'message': 'Unauthorized'}, 401)
    try:
        return _reply(kosync_service.push_progress(user['id'], request.get_json(silent=True) or {}))
    except ValueError as e:
        return _reply({'message': str(e)}, 400)


@kosync_bp.route('/kosync/syncs/progress/<string:document>', methods=['GET'])
def kosync_pull(document):
    user = _kosync_user()
    if not user:
        return _reply({'message': 'Unauthorized'}, 401)
    return _reply(kosync_service.pull_progress(user['id'], document))


# ---- 웹 계정 메뉴: 동기화 비밀번호 ----

def _session_user_id():
    user_id = session.get('user_id')
    return int(user_id) if user_id else None


@kosync_bp.route('/api/kosync/settings', methods=['GET'])
def kosync_settings_get():
    user_id = _session_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': '로그인이 필요합니다.'}), 401
    return jsonify({
        'success': True,
        'enabled': kosync_service.has_sync_password(user_id),
        'username': session.get('username') or '',
        'server_url': request.host_url.rstrip('/') + '/kosync',
    })


@kosync_bp.route('/api/kosync/settings', methods=['POST'])
def kosync_settings_set():
    user_id = _session_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': '로그인이 필요합니다.'}), 401
    password = (request.get_json(silent=True) or {}).get('password')
    try:
        kosync_service.set_sync_password(user_id, password)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    return jsonify({'success': True, 'enabled': True})


@kosync_bp.route('/api/kosync/settings', methods=['DELETE'])
def kosync_settings_clear():
    user_id = _session_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': '로그인이 필요합니다.'}), 401
    kosync_service.clear_sync_password(user_id)
    return jsonify({'success': True, 'enabled': False})
