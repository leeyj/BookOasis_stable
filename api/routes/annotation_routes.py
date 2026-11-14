# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
from api.helpers.route_helpers import session_user_info as _get_current_user_info, db_type_arg
from services.annotation_service import AnnotationService

annotation_bp = Blueprint('annotations', __name__)

def _get_target_db():
    return db_type_arg(('general', 'adult'))

@annotation_bp.route('/api/v1/books/<int:book_id>/annotations', methods=['GET'])
def get_book_annotations(book_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    db_type = _get_target_db()
    try:
        annotations = AnnotationService.get_book_annotations(db_type, book_id, user_id)
        return jsonify({'success': True, 'annotations': annotations})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@annotation_bp.route('/api/v1/books/<int:book_id>/annotations', methods=['POST'])
def create_annotation(book_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    db_type = _get_target_db()
    data = request.get_json() or {}
    try:
        annotation_id = AnnotationService.create_annotation(
            db_type, book_id, user_id,
            format=data.get('format'),
            chapter_idx=data.get('chapter_idx'),
            start_offset=data.get('start_offset'),
            end_offset=data.get('end_offset'),
            quote=data.get('quote'),
            prefix=data.get('prefix'),
            suffix=data.get('suffix'),
            color=data.get('color'),
            note=data.get('note'),
        )
        return jsonify({'success': True, 'annotation_id': annotation_id})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@annotation_bp.route('/api/v1/annotations/<int:annotation_id>', methods=['PUT'])
def update_annotation(annotation_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    db_type = _get_target_db()
    data = request.get_json() or {}
    try:
        success = AnnotationService.update_annotation(
            db_type, annotation_id, user_id,
            color=data.get('color'),
            note=data.get('note'),
        )
        return jsonify({'success': success})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@annotation_bp.route('/api/v1/annotations/<int:annotation_id>', methods=['DELETE'])
def delete_annotation(annotation_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    db_type = _get_target_db()
    try:
        success = AnnotationService.delete_annotation(db_type, annotation_id, user_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
