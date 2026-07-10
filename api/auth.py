# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template, g
from functools import wraps
import database
from werkzeug.security import generate_password_hash, check_password_hash
from services.settings_service import SettingsService
from repositories.user_repository import UserRepository

from utils.i18n_helper import get_available_languages
from utils.i18n import _t

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': _t('api.login_required')}), 401
            return redirect(url_for('media_api.auth.login'))
        
        # 기본 비밀번호 상태인데 비밀번호 변경 요청이 아닌 경우 차단
        if session.get('is_default_password') == 1 and request.endpoint != 'auth.change_password':
            # index 페이지(SPA 로더)는 허용하되, 데이터 조회용 API는 차단
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': _t('api.default_pw_change_required')}), 403
            
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({'success': False, 'error': _t('api.admin_required')}), 403
        return f(*args, **kwargs)
    return decorated_function

def check_adult_permission(db_type):
    if db_type == 'adult':
        # 어드민은 패스, 일반 유저는 세션의 has_adult_access 권한으로 판별
        if session.get('role') == 'admin':
            return True
        if session.get('has_adult_access') == 1:
            return True
        return False
    return True

@auth_bp.before_app_request
def check_authentication():
    # i18n 언어 스캔 API는 세션 예외
    if request.path == '/api/i18n/languages':
        return
        
    # 예외 대상 경로 리스트
    exempt_paths = [
        url_for('media_api.auth.login'),
        '/login',
        '/logout',
        '/change-password'
    ]
    
    # static 폴더, health 체크, OPDS/cover 경로 예외
    if (request.path.startswith('/static/')
            or request.path == '/health'
            or request.path.startswith('/opds')
            or request.path.startswith('/app-opds')   # 타치요미 전용 엔드포인트 (자체 인증 처리)
            or request.path.startswith('/covers')):
        return
        
    # 예외 경로 검사
    if request.path in exempt_paths:
        return
        
    # [프록시 헤더 인증 처리]
    if 'user_id' not in session:
        if SettingsService.get('PROXY_HEADER_AUTH', '0') == '1':
            remote_user = request.headers.get('Remote-User') or request.headers.get('X-Forwarded-User')
            if remote_user:
                user = UserRepository.find_by_username('general', remote_user)
                if user:
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user['role']
                    session['is_default_password'] = user['is_default_password']
        
    # 1. 미로그인 시 차단
    if 'user_id' not in session:
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': _t('api.login_required')}), 401
        return redirect(url_for('media_api.auth.login'))
        
    # 2. 기본 비밀번호 상태 시 일반 API 조회 차단
    if session.get('is_default_password') == 1:
        # index(SPA 로드)는 허용하여 변경 모달이 뜰 수 있도록 함
        if request.path in ['/', '/media-library']:
            return
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'is_default': True, 'error': _t('api.default_pw_change_required')}), 403

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # JSON 요청과 일반 Form 요청 모두 대응
        remember_me = False
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            remember_me = data.get('remember_me', False)
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            remember_me = request.form.get('remember_me') == 'on'
            
        if not username or not password:
            return jsonify({'success': False, 'error': _t('api.username_password_required')}), 400
            
        user = UserRepository.find_by_username('general', username)
        
        if user and check_password_hash(user['password_hash'], password):
            session.clear() # 세션 고정 취약점 방지
            
            # 자동 로그인이 체크된 경우 세션 만료기간을 연장 (기본적으로 Flask에서는 app.permanent_session_lifetime 에 따름, 보통 31일)
            if remember_me:
                session.permanent = True
                
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['is_default_password'] = user['is_default_password']
            session['has_adult_access'] = user['has_adult_access']
            
            return jsonify({
                'success': True,
                'role': user['role'],
                'is_default_password': user['is_default_password']
            })
        else:
            return jsonify({'success': False, 'error': _t('api.invalid_credentials')}), 401
            
    # GET 요청 시 로그인 템플릿 반환
    if 'user_id' in session:
        return redirect(url_for('media_api.media_admin.system.index'))
    return render_template('login.html')

@auth_bp.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('media_api.auth.login'))

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json() or {}
    new_password = data.get('new_password')
    
    if not new_password or len(new_password.strip()) < 4:
        return jsonify({'success': False, 'error': _t('api.new_password_length_error')}), 400
        
    user_id = session['user_id']
    new_hash = generate_password_hash(new_password.strip())
    
    # 두 DB 모두 계정을 동기화하여 비밀번호 변경 반영 (세션 일치)
    for db_type in ['general', 'adult']:
        UserRepository.update_password(db_type, user_id, new_hash)
        
    session['is_default_password'] = 0
    return jsonify({'success': True, 'message': _t('api.password_changed_success')})

# --- 어드민 전용 사용자 관리 API ---

@auth_bp.route('/api/admin/users', methods=['GET'])
@login_required
def get_users():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'error': _t('api.admin_required')}), 403
        
    users = UserRepository.get_all_users('general')
    return jsonify({'success': True, 'users': users})

@auth_bp.route('/api/admin/users', methods=['POST'])
@login_required
def add_user():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'error': _t('api.admin_required')}), 403
        
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user').strip()
    has_adult_access = 1 if data.get('has_adult_access', True) else 0
    
    if not username or not password:
        return jsonify({'success': False, 'error': _t('api.username_password_initial_required')}), 400
        
    if len(password) < 4:
        return jsonify({'success': False, 'error': _t('api.password_length_error')}), 400
        
    password_hash = generate_password_hash(password)
    
    try:
        # 동기화를 위해 두 데이터베이스에 모두 사용자 추가
        for db_type in ['general', 'adult']:
            UserRepository.add_user(db_type, username, password_hash, role, has_adult_access)
    except Exception as e:
        if 'UNIQUE' in str(e):
            return jsonify({'success': False, 'error': _t('api.username_exists')}), 409
        return jsonify({'success': False, 'error': _t('api.add_user_failed', error=str(e))}), 500
        
    return jsonify({'success': True, 'message': _t('api.user_added_success')})

@auth_bp.route('/api/admin/users/<int:target_user_id>', methods=['DELETE'])
@login_required
def delete_user(target_user_id):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'error': _t('api.admin_required')}), 403
        
    if session.get('user_id') == target_user_id:
        return jsonify({'success': False, 'error': _t('api.delete_self_error')}), 400
        
    # 두 데이터베이스 모두에서 삭제
    for db_type in ['general', 'adult']:
        UserRepository.delete_user(db_type, target_user_id)
        
    return jsonify({'success': True, 'message': _t('api.user_deleted_success')})

@auth_bp.route('/api/admin/users/<int:target_user_id>/password', methods=['PUT'])
@login_required
def reset_user_password(target_user_id):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'error': _t('api.admin_required')}), 403
        
    data = request.get_json() or {}
    new_password = data.get('new_password', '').strip()
    current_password = data.get('current_password', '').strip()
    
    if len(new_password) < 4:
        return jsonify({'success': False, 'error': _t('api.new_password_length_error')}), 400
        
    target_user = UserRepository.find_by_id('general', target_user_id)
    if not target_user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
        
    set_default = 1
    if target_user['role'] == 'admin':
        if not current_password:
            return jsonify({'success': False, 'error': _t('api.current_password_required', default='현재 비밀번호를 입력해주세요.')}), 400
        if not check_password_hash(target_user['password_hash'], current_password):
            return jsonify({'success': False, 'error': _t('api.invalid_current_password', default='현재 비밀번호가 일치하지 않습니다.')}), 401
        set_default = 0
        
    new_hash = generate_password_hash(new_password)
    
    for db_type in ['general', 'adult']:
        UserRepository.admin_reset_password(db_type, target_user_id, new_hash, set_default)
        
    return jsonify({'success': True, 'message': _t('api.password_changed_success')})

@auth_bp.route('/api/i18n/languages', methods=['GET'])
def get_languages():
    try:
        langs = get_available_languages()
        return jsonify({'success': True, 'languages': langs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
