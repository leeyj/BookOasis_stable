# -*- coding: utf-8 -*-
"""
problem_routes.py – 알림센터 문제 카드 조회/조치 API (관리자 전용)

재스캔은 기존 스캔 API(/api/media/libraries/<id>/scan, /scan-path, /api/media/books/scan-batch)를 그대로 쓴다.
여기에는 카드 상세 조회, 알고 있음(음소거), 대량 사라짐 확인 후 휴지통 이동, [해결됨], 도서 [진단]을 둔다.
예외로 [관리자에게 알리기](사용자 신고)는 로그인 사용자 누구나 부를 수 있다.
"""
from flask import Blueprint, jsonify, request, session

from api.auth import admin_required, check_adult_permission, login_required

problem_bp = Blueprint('problems', __name__)


def _group_key():
    payload = request.get_json(silent=True) or {}
    key = request.args.get('group_key') or payload.get('group_key') or ''
    key = str(key).strip()
    if not key or key.count('|') != 2 or len(key) > 255:
        return None
    return key


def _int_arg(name, default):
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


def _forget_card_cache():
    try:
        from services import notification_service
        notification_service._cards_cache['at'] = 0.0
    except Exception:
        pass


@problem_bp.route('/api/problems/card', methods=['GET'])
@admin_required
def get_problem_card():
    key = _group_key()
    if not key:
        return jsonify({'success': False, 'error': 'group_key가 필요합니다.'}), 400
    from services.problem_card_service import get_card
    data = get_card(key, offset=_int_arg('offset', 0), limit=_int_arg('limit', 50))
    if data is None:
        return jsonify({'success': False, 'error': '이미 해결된 카드입니다.', 'resolved': True}), 404
    return jsonify({'success': True, **data})


@problem_bp.route('/api/problems/card/items', methods=['GET'])
@admin_required
def get_problem_card_items():
    key = _group_key()
    if not key:
        return jsonify({'success': False, 'error': 'group_key가 필요합니다.'}), 400
    from services.problem_card_service import get_card_items
    data = get_card_items(key, series_key=request.args.get('series_key') or None,
                          offset=_int_arg('offset', 0), limit=_int_arg('limit', 50))
    if data is None:
        return jsonify({'success': False, 'error': '이미 해결된 카드입니다.', 'resolved': True}), 404
    return jsonify({'success': True, **data})


@problem_bp.route('/api/problems/card/mute', methods=['POST'])
@admin_required
def mute_problem_card():
    key = _group_key()
    if not key:
        return jsonify({'success': False, 'error': 'group_key가 필요합니다.'}), 400
    from services.problem_service import ProblemService
    payload = request.get_json(silent=True) or {}
    if payload.get('unmute'):
        ProblemService.unmute_card(key)
    elif not ProblemService.mute_card(key):
        return jsonify({'success': False, 'error': '이미 해결된 카드입니다.'}), 404
    _forget_card_cache()
    return jsonify({'success': True})


@problem_bp.route('/api/problems/card/confirm-trash', methods=['POST'])
@admin_required
def confirm_trash_problem_card():
    key = _group_key()
    if not key:
        return jsonify({'success': False, 'error': 'group_key가 필요합니다.'}), 400
    from services.scan_problem_service import confirm_trash
    try:
        result = confirm_trash(key)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'success': False, 'error': str(e)}), 409
    _forget_card_cache()
    return jsonify({'success': True, **result})


@problem_bp.route('/api/problems/card/resolve', methods=['POST'])
@admin_required
def resolve_problem_card():
    """[해결됨]: 사용자 신고 카드처럼 스캐너가 자동 해제할 수 없는 카드를 관리자가 닫는다."""
    key = _group_key()
    if not key:
        return jsonify({'success': False, 'error': 'group_key가 필요합니다.'}), 400
    from services.problem_service import ProblemService
    try:
        resolved = ProblemService.resolve_card(key)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    _forget_card_cache()
    return jsonify({'success': True, 'resolved': resolved})


@problem_bp.route('/api/problems/diagnose', methods=['GET'])
@admin_required
def diagnose_book():
    """도서 1권 [진단] 체크리스트 (services/book_diagnosis_service.py, MCP diagnose_book과 같은 결과)."""
    from services.book_diagnosis_service import diagnose_book as run
    db_type = request.args.get('type', 'general')
    try:
        book_id = int(request.args.get('book_id', ''))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'book_id가 필요합니다.'}), 400
    try:
        return jsonify({'success': True, **run(db_type, book_id)})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@problem_bp.route('/api/problems/user-report', methods=['POST'])
@login_required
def user_report():
    """[관리자에게 알리기]: 뷰어 오류 자리에서 일반 사용자가 보낸 신고를 문제 카드로 남긴다."""
    from services.user_problem_report_service import ReportRejected, report_book_problem
    payload = request.get_json(silent=True) or {}
    db_type = str(payload.get('type') or 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403
    try:
        result = report_book_problem(
            user_id=session.get('user_id'), username=session.get('username'), role=session.get('role'),
            db_type=db_type, book_id=payload.get('book_id'), where=payload.get('where') or 'viewer',
            message=payload.get('message') or '', file_format=payload.get('format') or '',
        )
    except ReportRejected as e:
        return jsonify({'success': False, 'error': str(e)}), e.status
    return jsonify({'success': True, **result})
