# -*- coding: utf-8 -*-
"""
gdrive_copy_routes.py – 구글 드라이브 서버사이드 복사(2단계: 리모트 감지/선택/검증) 라우터

실험적 기능이라 DEVELOP=true 환경에서만 라우트 자체를 노출한다 (다른 gdrive 관련 기능이
템플릿 레벨에서만 숨겨지는 것과 달리, 이 라우트는 OAuth 자격증명을 다루므로 서버 측에서도 가드).
"""
import os
from flask import Blueprint, request, jsonify
from api.auth import admin_required
from utils.rclone_gdrive_copy import list_writable_drive_remotes, validate_remote_access
from services.gdrive_copy_service import GdriveCopyService

gdrive_copy_bp = Blueprint('gdrive_copy', __name__)


def _develop_mode_enabled():
    return os.environ.get('DEVELOP', 'false').lower() == 'true'


@gdrive_copy_bp.route('/api/gdrive-copy/remotes', methods=['GET'])
@admin_required
def get_gdrive_copy_remotes():
    if not _develop_mode_enabled():
        return jsonify({'success': False, 'error': '지원하지 않는 기능입니다.'}), 404
    try:
        remotes = list_writable_drive_remotes()
        return jsonify({'success': True, 'remotes': remotes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@gdrive_copy_bp.route('/api/gdrive-copy/validate', methods=['POST'])
@admin_required
def validate_gdrive_copy_target():
    if not _develop_mode_enabled():
        return jsonify({'success': False, 'error': '지원하지 않는 기능입니다.'}), 404

    data = request.get_json(silent=True) or {}
    remote_name = str(data.get('remote') or '').strip()
    dest_path = str(data.get('dest_path') or '').strip()

    if not remote_name:
        return jsonify({'success': False, 'error': '리모트를 선택해 주세요.'}), 400
    if len(dest_path) > 1024:
        return jsonify({'success': False, 'error': '목적지 경로가 너무 깁니다.'}), 400

    try:
        result = validate_remote_access(remote_name, dest_path)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@gdrive_copy_bp.route('/api/gdrive-copy/detect-mount-root', methods=['POST'])
@admin_required
def detect_gdrive_copy_mount_root():
    """물리 경로가 이미 rclone으로 마운트돼 있는 위치라면, rclone RC의 mount/listmounts로
    실제 마운트 루트를 조회해 돌려준다 — 관리자가 "이 리모트가 로컬 어디에 마운트돼
    있는지"를 직접 입력하지 않아도, rclone 자신이 이미 아는 정보를 그대로 재사용한다.

    physical_path는 선택 값이다 — 여러 마운트 지점 중 하나를 골라내는 부가 필터일 뿐,
    remote_name만으로도 /proc/mounts 조회는 그대로 동작한다(뷰어 전용 카테고리는 애초에
    복사 목적지와 무관한 물리 경로를 갖고 있어 이 값이 없는 게 정상)."""
    if not _develop_mode_enabled():
        return jsonify({'success': False, 'error': '지원하지 않는 기능입니다.'}), 404

    data = request.get_json(silent=True) or {}
    db_type = str(data.get('type') or 'general')
    physical_path = str(data.get('physical_path') or '').strip()
    rclone_rc_url = str(data.get('rclone_rc_url') or '').strip()
    remote_name = str(data.get('remote') or '').strip()

    if not remote_name:
        return jsonify({'success': False, 'error': '리모트를 선택해 주세요.'}), 400

    print(f"[GdriveCopy-MountDetect] 요청 수신: type='{db_type}', remote='{remote_name}', physical_path='{physical_path}', rclone_rc_url(요청값)='{rclone_rc_url}'")

    try:
        from tools.scanner.vfs import detect_mount_root, resolve_rc_urls
        rc_urls = resolve_rc_urls(db_type, {'rclone_rc_url': rclone_rc_url})
        print(f"[GdriveCopy-MountDetect] 최종 조회 대상 RC URL 목록: {rc_urls}")
        mount_root = detect_mount_root(remote_name, physical_path, rc_urls)
        if mount_root:
            return jsonify({'success': True, 'mount_root': mount_root})
        return jsonify({'success': False, 'error': 'RC 서버에서 이 경로를 포함하는 마운트를 찾지 못했습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@gdrive_copy_bp.route('/api/gdrive-copy/start', methods=['POST'])
@admin_required
def start_gdrive_copy():
    if not _develop_mode_enabled():
        return jsonify({'success': False, 'error': '지원하지 않는 기능입니다.'}), 404

    data = request.get_json(silent=True) or {}
    db_type = str(data.get('type') or 'general')

    try:
        GdriveCopyService.start_gdrive_copy_job(
            db_type=db_type,
            remote=data.get('remote'),
            dest_local_path=data.get('dest_local_path'),
            rclone_rc_url=data.get('rclone_rc_url'),
            source_links=data.get('source_links'),
        )
        return jsonify({'success': True, 'message': 'Drive 복사 작업을 시작했습니다.'})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
