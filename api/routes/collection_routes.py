# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
from services.collection_service import CollectionService

collection_bp = Blueprint('collections', __name__)

def _get_current_user_info():
    user_id = session.get('user_id')
    role = session.get('role')
    if not user_id:
        user_dict = session.get('user')
        if isinstance(user_dict, dict):
            user_id = user_dict.get('id')
            role = user_dict.get('role')
    return user_id, role

def _get_target_db():
    raw_type = request.args.get('db_type', 'general')
    if raw_type not in ('general', 'adult', 'audiobook'):
        return 'general'
    return raw_type

@collection_bp.route('/api/v1/collections', methods=['GET'])
def get_collections():
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    db_type = _get_target_db()
    try:
        colls = CollectionService.get_user_collections(db_type, user_id)
        return jsonify({'success': True, 'collections': colls})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@collection_bp.route('/api/v1/collections', methods=['POST'])
def create_collection():
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    db_type = _get_target_db()
    data = request.get_json() or {}
    name = data.get('name')
    description = data.get('description')
    color = data.get('color', '#7c3aed')

    try:
        coll_id = CollectionService.create_collection(db_type, user_id, name, description, color)
        return jsonify({'success': True, 'collection_id': coll_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@collection_bp.route('/api/v1/collections/<int:collection_id>', methods=['GET'])
def get_collection_detail(collection_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    db_type = _get_target_db()
    try:
        detail = CollectionService.get_collection_detail(db_type, collection_id, user_id)
        return jsonify({'success': True, 'collection': detail})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@collection_bp.route('/api/v1/collections/<int:collection_id>', methods=['PUT'])
def update_collection(collection_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    db_type = _get_target_db()
    data = request.get_json() or {}
    name = data.get('name')
    description = data.get('description')
    color = data.get('color', '#7c3aed')

    try:
        success = CollectionService.update_collection(db_type, collection_id, user_id, name, description, color)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@collection_bp.route('/api/v1/collections/<int:collection_id>', methods=['DELETE'])
def delete_collection(collection_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    db_type = _get_target_db()
    try:
        success = CollectionService.delete_collection(db_type, collection_id, user_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@collection_bp.route('/api/v1/collections/<int:collection_id>/items', methods=['POST'])
def add_collection_item(collection_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    db_type = _get_target_db()
    data = request.get_json() or {}
    book_id = data.get('book_id')
    series_name = data.get('series_name')
    audiobook_id = data.get('audiobook_id')

    try:
        item_id = CollectionService.add_item(db_type, collection_id, user_id, book_id, series_name, audiobook_id)
        return jsonify({'success': True, 'item_id': item_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@collection_bp.route('/api/v1/collections/<int:collection_id>/items/<int:item_id>', methods=['DELETE'])
def remove_collection_item(collection_id, item_id):
    user_id, role = _get_current_user_info()
    if not user_id:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    db_type = _get_target_db()
    try:
        success = CollectionService.remove_item(db_type, collection_id, user_id, item_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
