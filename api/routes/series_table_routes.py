# -*- coding: utf-8 -*-
"""관리자 테이블 뷰 API - 시리즈 표 조회 / 셀 저장 / CSV 내보내기 (일반·성인 도서)."""
from datetime import datetime

from flask import Blueprint, Response, request, jsonify, stream_with_context

from api.auth import admin_required, check_adult_permission
from services.series_table_service import SeriesTableService, SummaryNotReady
from utils.i18n import _t

series_table_bp = Blueprint('media_series_table_routes', __name__)

_NOT_READY_MESSAGE = '시리즈 요약을 만드는 중입니다. 잠시 후 다시 시도해 주세요.'


def _split(raw):
    return [token.strip() for token in str(raw or '').split(',') if token.strip()]


def _filters_from_args():
    return {
        'library_id': request.args.get('library_id'),
        'sort': request.args.get('sort'),
        'direction': request.args.get('dir'),
        'missing': _split(request.args.get('missing')),
        'search': request.args.get('search', '').strip(),
        'genres': _split(request.args.get('genres')),
        'tags': _split(request.args.get('tags')),
        'filter_mode': 'or' if request.args.get('filter_mode', '').strip().lower() == 'or' else 'and',
    }


@series_table_bp.route('/api/admin/series-table', methods=['GET'])
@admin_required
def get_series_table():
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
    except ValueError:
        page, limit = 1, 100
    try:
        result = SeriesTableService.list_rows(db_type, page=page, limit=limit, **_filters_from_args())
        return jsonify({'success': True, **result})
    except SummaryNotReady:
        return jsonify({'success': False, 'error': _NOT_READY_MESSAGE}), 503
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@series_table_bp.route('/api/admin/series-table/cell', methods=['POST'])
@admin_required
def save_series_table_cell():
    data = request.get_json(silent=True) or request.form
    db_type = data.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    try:
        result = SeriesTableService.save_cell(
            db_type, data.get('series_name'), data.get('field'), data.get('value'),
            library_id=data.get('library_id'),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@series_table_bp.route('/api/admin/series-table/export', methods=['GET'])
@admin_required
def export_series_table():
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    try:
        chunks = SeriesTableService.iter_csv(db_type, columns=_split(request.args.get('columns')), **_filters_from_args())
    except SummaryNotReady:
        return jsonify({'success': False, 'error': _NOT_READY_MESSAGE}), 503
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    filename = f"bookoasis_series_{db_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        stream_with_context(chunk.encode('utf-8') for chunk in chunks),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'no-store'},
    )
