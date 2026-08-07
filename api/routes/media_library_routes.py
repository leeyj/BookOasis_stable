# -*- coding: utf-8 -*-
import sqlite3
import time
from flask import Blueprint, request, jsonify, session

from services.category_service import CategoryService
from services.series_service import SeriesService
from services.book_detail_service import BookDetailService
from services.reading_history_service import ReadingHistoryService
from services.library_service import LibraryService
from api.auth import login_required, check_adult_permission
from utils.i18n import _t

media_library_routes_bp = Blueprint('media_library_browse_routes', __name__)

@media_library_routes_bp.route('/api/media/libraries', methods=['GET'])
@login_required
def get_media_libraries():
    """라이브러리 카테고리 목록 조회"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    try:
        user_id = session.get('user_id')
        role = session.get('role')
        libraries = CategoryService.get_libraries(db_type, user_id=user_id, role=role)
        return jsonify({'success': True, 'libraries': libraries})
    except sqlite3.OperationalError as e:
        msg = str(e)
        lock_like = ('locked' in msg.lower()) or ('pool exhausted' in msg.lower()) or ('timeout waiting for connection' in msg.lower())
        if lock_like:
            return jsonify({
                'success': True,
                'libraries': [],
                'degraded': True,
                'warning': 'DB가 일시적으로 혼잡합니다. 잠시 후 자동 재시도하거나 새로고침 해주세요.'
            })
        return jsonify({'success': False, 'error': msg}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@media_library_routes_bp.route('/api/media/list', methods=['GET'])
@login_required
def get_media_list():
    """도서 보관함 시리즈 목록 조회 (무한 스크롤 페이지네이션 + 서버 검색)"""
    t_start = time.perf_counter()
    db_type    = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    library_id = request.args.get('library_id')
    search_query = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'asc').strip().lower()
    user_id = session.get('user_id')
    role = session.get('role')
    try:
        page  = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 30))
    except ValueError:
        page, limit = 1, 30

    try:
        series_list = SeriesService.get_books_list(
            db_type,
            library_id,
            page,
            limit,
            search_query,
            sort,
            user_id=user_id,
            role=role
        )
        has_more = len(series_list) > limit
        if has_more:
            series_list = series_list[:limit]
        t_end = time.perf_counter()
        print(f"[API-PROFILE] GET /api/media/list (type={db_type}, lib={library_id}, page={page}) -> TOTAL HTTP RESPONSE: {(t_end - t_start)*1000:.1f}ms")
        return jsonify({'success': True, 'series': series_list, 'has_more': has_more})
    except Exception as e:
        err_msg = str(e)
        if 'malformed' in err_msg.lower() or 'locked' in err_msg.lower():
            err_msg = '스캔 작업으로 데이터베이스가 잠시 바쁩니다. 잠시 후 다시 시도해 주세요.'
        return jsonify({'success': False, 'error': err_msg}), 500

@media_library_routes_bp.route('/api/media/all-list', methods=['GET'])
@login_required
def get_media_all_list():
    """Kavita 방식의 선로드를 위해 특정 라이브러리의 전체 시리즈 목록을 페이징 없이 경량 조회"""
    t_start = time.perf_counter()
    db_type    = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    library_id = request.args.get('library_id')
    user_id = session.get('user_id', 1)
    role = session.get('role')
    try:
        series_list = SeriesService.get_all_books_list(
            db_type,
            library_id,
            user_id=user_id,
            role=role
        )
        t_end = time.perf_counter()
        print(f"[API-PROFILE] GET /api/media/all-list (type={db_type}, lib={library_id}) -> TOTAL HTTP RESPONSE: {(t_end - t_start)*1000:.1f}ms")
        return jsonify({'success': True, 'series': series_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@media_library_routes_bp.route('/api/media/detail', methods=['GET'])
@login_required
def get_media_detail():
    """특정 시리즈 상세 정보 및 단행본 목록 조회"""
    db_type     = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    series_name = request.args.get('series', '')
    library_id  = request.args.get('library_id', 'all')
    representative_book_id = request.args.get('representative_book_id')
    user_id     = session.get('user_id', 1)
    role        = session.get('role')

    try:
        meta, books_list = BookDetailService.get_media_detail(
            db_type,
            series_name,
            library_id,
            user_id=user_id,
            role=role,
            representative_book_id=representative_book_id
        )
        return jsonify({'success': True, 'meta': meta, 'books': books_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@media_library_routes_bp.route('/api/media/tags', methods=['GET'])
@login_required
def get_media_tags():
    """도서 보관함의 전체 유니크 태그 목록 조회"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    library_id = request.args.get('library_id')
    
    try:
        tags = LibraryService.get_media_tags(db_type, library_id)
        return jsonify({'success': True, 'tags': tags})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@media_library_routes_bp.route('/api/media/genres', methods=['GET'])
@login_required
def get_media_genres():
    """도서 보관함의 전체 유니크 장르 목록 조회"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    library_id = request.args.get('library_id')
    
    try:
        genres = LibraryService.get_media_genres(db_type, library_id)
        return jsonify({'success': True, 'genres': genres})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@media_library_routes_bp.route('/api/media/history', methods=['GET'])
@login_required
def get_media_history():
    """최근 읽은 도서 히스토리 (최대 20건)"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    try:
        history = ReadingHistoryService.get_history(db_type, user_id=user_id)
        return jsonify({'success': True, 'books': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@media_library_routes_bp.route('/api/media/recently-added', methods=['GET'])
@login_required
def get_media_recently_added():
    """신규 추가 도서 (최대 20건)"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    try:
        user_id = session.get('user_id')
        role = session.get('role')
        books = ReadingHistoryService.get_recently_added(db_type, user_id=user_id, role=role)
        return jsonify({'success': True, 'books': books})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@media_library_routes_bp.route('/api/category/test-gdrive-links', methods=['POST'])
@login_required
def test_gdrive_links_api():
    """구글 드라이브 공유 링크 테스트 엔드포인트"""
    data = request.get_json() or {}
    links = data.get('links', '')
    if not links.strip():
        return jsonify({'success': False, 'error': '테스트할 구글 드라이브 공유 링크를 입력해 주세요.'})
    
    import re
    folder_ids = []
    for line in links.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.search(r'folders/([a-zA-Z0-9_-]+)', line)
        if match:
            folder_ids.append(match.group(1))
        elif re.match(r'^[a-zA-Z0-9_-]{20,}$', line):
            folder_ids.append(line)
            
    if not folder_ids:
        return jsonify({'success': False, 'error': '유효한 구글 드라이브 폴더 링크나 ID를 찾지 못했습니다.'})
        
    return jsonify({
        'success': True,
        'message': f'{len(folder_ids)}개의 구글 드라이브 공유 폴더 ID가 감지되었습니다. (정상 감지)'
    })
