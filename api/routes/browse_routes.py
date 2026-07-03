# -*- coding: utf-8 -*-
"""
browse_routes.py – 경로 탐색 라우터 (로컬 파일시스템)
"""
import os
from flask import Blueprint, request, jsonify
from api.auth import admin_required

browse_bp = Blueprint('browse', __name__)

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

def _browse_local(path):
    """로컬 파일시스템 탐색"""
    if not os.path.exists(path):
        # 기본 경로에서 시작
        if os.name == 'nt':  # Windows
            drives = []
            for drive_letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                drive_path = f"{drive_letter}:\\"
                if os.path.exists(drive_path):
                    drives.append({
                        'name': drive_letter,
                        'path': drive_path,
                        'isDir': True
                    })
            return jsonify({'success': True, 'items': drives, 'currentPath': ''})
        else:  # Linux/macOS
            path = os.path.expanduser('~')
    
    # 경로 정규화 (상대경로 → 절대경로)
    path = os.path.abspath(path)
    
    # 디렉토리 내용 읽기
    if not os.path.isdir(path):
        return jsonify({'success': False, 'error': f'경로가 디렉토리가 아닙니다: {path}'}), 400
    
    dirs = []
    try:
        entries = os.listdir(path)
        for entry in entries:
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                dirs.append({
                    'name': entry,
                    'path': full_path,
                    'isDir': True
                })
    except PermissionError:
        return jsonify({'success': False, 'error': f'접근 권한 없음: {path}'}), 403
    except Exception as e:
        return jsonify({'success': False, 'error': f'디렉토리 읽기 오류: {str(e)}'}), 400
    
    # 상위 디렉토리 (..) 추가
    parent = os.path.dirname(path)
    if parent != path:  # root 제외
        dirs.insert(0, {'name': '..', 'path': parent, 'isDir': True})
    
    # 정렬
    dirs.sort(key=lambda x: (x['name'] != '..', x['name'].lower()))
    
    return jsonify({'success': True, 'items': dirs, 'currentPath': path})
