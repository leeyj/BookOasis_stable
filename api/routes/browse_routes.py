# -*- coding: utf-8 -*-
"""
browse_routes.py – 경로 탐색 라우터 (로컬 파일시스템)
"""
import os
from flask import Blueprint, request, jsonify
from api.auth import admin_required

browse_bp = Blueprint('browse', __name__)
MAX_BROWSE_PATH_LENGTH = 1024

@browse_bp.route('/api/media/browse-paths', methods=['GET'])
@admin_required
def browse_paths():
    """경로 탐색 (로컬 파일시스템 지원)"""
    path = request.args.get('path', '').strip()
    
    if not path:
        path = '.'
    
    try:
        # 로컬 파일시스템 탐색만 지원
        # TODO: rclone RC API 지원은 향후 추가 예정
        return _browse_local(path)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'예상치 못한 오류: {str(e)}'}), 500


def _norm_abs(path_value):
    return os.path.normcase(os.path.realpath(os.path.abspath(path_value)))


def _get_allowed_roots():
    """관리자 탐색 허용 루트 목록을 반환합니다.

    - 환경변수 `BROWSE_ALLOWED_ROOTS` (os.pathsep 구분) 우선
    - 미설정 시: Windows는 존재하는 드라이브 루트, POSIX는 '/'
    """
    env_val = str(os.environ.get('BROWSE_ALLOWED_ROOTS', '')).strip()
    roots = []
    if env_val:
        for item in env_val.split(os.pathsep):
            item = item.strip()
            if item:
                roots.append(_norm_abs(os.path.expanduser(item)))
        if roots:
            return roots

    if os.name == 'nt':
        for drive_letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive_path = f"{drive_letter}:\\"
            if os.path.exists(drive_path):
                roots.append(_norm_abs(drive_path))
        return roots

    return [_norm_abs('/')]


def _is_under_allowed_roots(path_value, allowed_roots):
    path_norm = _norm_abs(path_value)
    for root in allowed_roots:
        try:
            if os.path.commonpath([path_norm, root]) == root:
                return True
        except ValueError:
            continue
    return False


def _resolve_request_path(raw_path):
    text = str(raw_path or '').strip()
    if '\x00' in text:
        raise ValueError('경로에 허용되지 않는 NULL 문자가 포함되어 있습니다.')
    if len(text) > MAX_BROWSE_PATH_LENGTH:
        raise ValueError(f'경로 입력 길이는 최대 {MAX_BROWSE_PATH_LENGTH}자까지 허용됩니다.')
    if not text:
        return ''
    if text == '.':
        return _norm_abs(os.getcwd())
    return _norm_abs(os.path.expanduser(text))


def _list_root_entries(allowed_roots):
    items = []
    for root in allowed_roots:
        if os.path.exists(root):
            label = root
            if os.name == 'nt' and len(root) >= 2 and root[1] == ':':
                label = root[0].upper()
            items.append({'name': label, 'path': root, 'isDir': True})
    items.sort(key=lambda x: x['name'].lower())
    return jsonify({'success': True, 'items': items, 'currentPath': ''})

def _browse_local(path):
    """로컬 파일시스템 탐색"""
    allowed_roots = _get_allowed_roots()
    try:
        resolved_path = _resolve_request_path(path)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    if not resolved_path:
        return _list_root_entries(allowed_roots)

    if not _is_under_allowed_roots(resolved_path, allowed_roots):
        return jsonify({'success': False, 'error': f'허용되지 않은 경로입니다: {resolved_path}'}), 403

    if not os.path.exists(resolved_path):
        # 존재하지 않는 경로 요청 시 루트 선택 화면으로 복귀
        return _list_root_entries(allowed_roots)
    
    # 디렉토리 내용 읽기
    if not os.path.isdir(resolved_path):
        return jsonify({'success': False, 'error': f'경로가 디렉토리가 아닙니다: {resolved_path}'}), 400
    
    dirs = []
    try:
        entries = os.listdir(resolved_path)
        for entry in entries:
            full_path = _norm_abs(os.path.join(resolved_path, entry))
            if os.path.isdir(full_path):
                dirs.append({
                    'name': entry,
                    'path': full_path,
                    'isDir': True
                })
    except PermissionError:
        return jsonify({'success': False, 'error': f'접근 권한 없음: {resolved_path}'}), 403
    except Exception as e:
        return jsonify({'success': False, 'error': f'디렉토리 읽기 오류: {str(e)}'}), 400
    
    # 상위 디렉토리 (..) 추가
    parent = _norm_abs(os.path.dirname(resolved_path))
    if parent != resolved_path and _is_under_allowed_roots(parent, allowed_roots):
        dirs.insert(0, {'name': '..', 'path': parent, 'isDir': True})
    
    # 정렬
    dirs.sort(key=lambda x: (x['name'] != '..', x['name'].lower()))
    
    return jsonify({'success': True, 'items': dirs, 'currentPath': resolved_path})
