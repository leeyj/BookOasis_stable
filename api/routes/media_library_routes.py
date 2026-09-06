# -*- coding: utf-8 -*-
import sqlite3
import time
from flask import Blueprint, request, jsonify, session

from services.category_service import CategoryService
from services.series_service import SeriesService
from services.book_detail_service import BookDetailService
from services.reading_history_service import ReadingHistoryService
from services.library_service import LibraryService
from services.recommendation_service import RecommendationService
from api.auth import login_required, check_adult_permission
from utils.i18n import _t

media_library_routes_bp = Blueprint('media_library_browse_routes', __name__)


def _parse_csv_filter_values(raw_value):
    if not raw_value:
        return []
    values = []
    for token in str(raw_value).split(','):
        normalized = token.strip()
        if normalized:
            values.append(normalized)
    return values

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
        visible_group_ids = {library.get('group_id') for library in libraries if library.get('group_id') is not None}
        groups = [
            group for group in CategoryService.get_library_groups(db_type)
            if role == 'admin' or group.get('id') in visible_group_ids
        ]
        return jsonify({'success': True, 'libraries': libraries, 'groups': groups})
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
    genre_filters = _parse_csv_filter_values(request.args.get('genres', ''))
    tag_filters = _parse_csv_filter_values(request.args.get('tags', ''))
    group_by = request.args.get('group_by', '').strip()
    author_key = request.args.get('author_key', '').strip()
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
            genre_filters=genre_filters,
            tag_filters=tag_filters,
            user_id=user_id,
            role=role,
            group_by=group_by,
            author_key=author_key
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

@media_library_routes_bp.route('/api/media/list/jump', methods=['GET'])
@login_required
def get_media_list_jump_position():
    """초성(가나다) 바로가기: 대상 글자로 시작하는 첫 항목의 페이지/오프셋을 계산해 반환"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    library_id = request.args.get('library_id')
    search_query = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'asc').strip().lower()
    target_char = request.args.get('char', '').strip()
    genre_filters = _parse_csv_filter_values(request.args.get('genres', ''))
    tag_filters = _parse_csv_filter_values(request.args.get('tags', ''))
    user_id = session.get('user_id')
    role = session.get('role')
    try:
        limit = int(request.args.get('limit', 30))
    except ValueError:
        limit = 30

    if not target_char:
        return jsonify({'success': False, 'error': 'char is required'}), 400

    try:
        result = SeriesService.find_jump_position(
            db_type,
            library_id,
            search_query,
            sort,
            target_char,
            limit,
            genre_filters=genre_filters,
            tag_filters=tag_filters,
            user_id=user_id,
            role=role
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@media_library_routes_bp.route('/api/media/list-totals', methods=['GET'])
@login_required
def get_media_list_totals():
    """현재 목록 조건의 전체 시리즈/권 수를 목록 페이지 조회와 분리해 반환합니다."""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    library_id = request.args.get('library_id')
    search_query = request.args.get('search', '').strip()
    genre_filters = _parse_csv_filter_values(request.args.get('genres', ''))
    tag_filters = _parse_csv_filter_values(request.args.get('tags', ''))
    try:
        totals = SeriesService.get_books_totals(
            db_type,
            library_id,
            search_query=search_query,
            genre_filters=genre_filters,
            tag_filters=tag_filters,
            user_id=session.get('user_id'),
            role=session.get('role'),
        )
        return jsonify({'success': True, **totals})
    except Exception as error:
        return jsonify({'success': False, 'error': str(error)}), 500

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

@media_library_routes_bp.route('/api/media/recommendations', methods=['GET'])
@login_required
def get_smart_recommendations():
    """읽은 시리즈 기준 장르/태그 겹침 스마트 추천"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    series_name = request.args.get('series_name')
    library_id = request.args.get('library_id')
    if not series_name:
        return jsonify({'success': False, 'error': 'series_name is required'}), 400
    user_id = session.get('user_id', 1)
    try:
        data = RecommendationService.get_similar_series(db_type, series_name, library_id, user_id=user_id)
        return jsonify({'success': True, **data})
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
