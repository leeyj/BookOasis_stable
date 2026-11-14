# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
from api.helpers.route_helpers import session_user_info as _get_current_user_info, db_type_arg
from services.bookmark_service import BookmarkService

bookmark_bp = Blueprint('bookmarks', __name__)

def _get_target_db():
    return db_type_arg(('general', 'adult'))

@bookmark_bp.route('/api/v1/books/<int:book_id>/bookmarks', methods=['GET'])
def get_book_bookmarks(book_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    db_type = _get_target_db()
    try:
        bookmarks = BookmarkService.get_book_bookmarks(db_type, book_id, user_id)
        return jsonify({'success': True, 'bookmarks': bookmarks})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bookmark_bp.route('/api/v1/books/<int:book_id>/bookmarks', methods=['POST'])
def create_bookmark(book_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    db_type = _get_target_db()
    data = request.get_json() or {}
    try:
        bookmark_id = BookmarkService.create_bookmark(
            db_type, book_id, user_id,
            format=data.get('format'),
            chapter_idx=data.get('chapter_idx'),
            percent=data.get('percent'),
            label=data.get('label'),
        )
        return jsonify({'success': True, 'bookmark_id': bookmark_id})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bookmark_bp.route('/api/v1/bookmarks/<int:bookmark_id>', methods=['DELETE'])
def delete_bookmark(bookmark_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    db_type = _get_target_db()
    try:
        success = BookmarkService.delete_bookmark(db_type, bookmark_id, user_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
