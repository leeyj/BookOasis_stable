# -*- coding: utf-8 -*-
"""
report_routes.py – 스캔 에러 리포트 조회 라우터
"""
import os
import json
import glob
import re
from flask import Blueprint, request, jsonify
from api.auth import admin_required
from utils.i18n import _t

report_bp = Blueprint('report', __name__)

_SAFE_REPORT_FILENAME_RE = re.compile(r'^[A-Za-z0-9_-]+\.json$')


def _resolve_report_file_path(user_filename):
    """사용자 입력 파일명을 reports 디렉토리 내부의 안전한 절대경로로 변환합니다."""
    filename = os.path.basename(str(user_filename or '').strip())
    if not filename:
        raise ValueError(_t('api.err_filename_param_invalid'))
    if '\x00' in filename:
        raise ValueError(_t('api.err_filename_param_invalid'))
    if not _SAFE_REPORT_FILENAME_RE.match(filename):
        raise ValueError(_t('api.err_filename_param_invalid'))

    from utils.report_helper import get_reports_dir
    reports_dir = os.path.realpath(get_reports_dir())
    filepath = os.path.realpath(os.path.join(reports_dir, filename))
    if os.path.commonpath([filepath, reports_dir]) != reports_dir:
        raise ValueError(_t('api.err_filename_param_invalid'))

    return filepath, filename

@report_bp.route('/api/media/libraries/<int:library_id>/reports', methods=['GET'])
@admin_required
def get_library_reports(library_id):
    """특정 라이브러리 카테고리의 스캔 에러 리포트 목록 조회"""
    try:
        from utils.report_helper import get_reports_dir
        reports_dir = get_reports_dir()
        pattern = os.path.join(reports_dir, f"{library_id}_*.json")
        files = glob.glob(pattern)
        # 파일명 기준 역순(최신순) 정렬
        files.sort(key=os.path.basename, reverse=True)
        
        report_list = []
        for filepath in files:
            filename = os.path.basename(filepath)
            formatted_time = _parse_report_timestamp(filename)
            errors_count = _get_report_error_count(filepath)
            
            report_list.append({
                'filename': filename,
                'timestamp': formatted_time,
                'errors_count': errors_count
            })
        return jsonify({'success': True, 'reports': report_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@report_bp.route('/api/media/libraries/reports/view', methods=['GET'])
@admin_required
def view_report_detail():
    """특정 리포트 파일의 에러 리스트 상세 조회"""
    user_file = request.args.get('file', '').strip()
    
    try:
        filepath, _ = _resolve_report_file_path(user_file)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': _t('api.err_report_not_found')}), 404
        
        with open(filepath, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        return jsonify({'success': True, 'report': report_data})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _parse_report_timestamp(filename):
    """리포트 파일명에서 타임스탬프 파싱"""
    try:
        parts = filename.replace('.json', '').split('_')
        timestamp_str = parts[-1] if len(parts) > 1 else ''
        return f"{timestamp_str[0:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]} {timestamp_str[8:10]}:{timestamp_str[10:12]}:{timestamp_str[12:14]}"
    except Exception:
        return timestamp_str if 'timestamp_str' in locals() else '-'

def _get_report_error_count(filepath):
    """리포트 파일에서 에러 개수 조회"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('errors_count', 0)
    except Exception:
        return 0
