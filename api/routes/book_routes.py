# -*- coding: utf-8 -*-
import os
import mimetypes
from flask import Blueprint, request, jsonify, session, send_file

from services.book_service import BookService
from services.book_detail_service import BookDetailService
from services.metadata_service import MetadataService
from services.book_info_service import BookInfoService
from api.auth import login_required, check_adult_permission, admin_required
from utils.i18n import _t

book_routes_bp = Blueprint('media_book_routes', __name__)

@book_routes_bp.route('/api/media/detail/edit', methods=['POST'])
@admin_required
def edit_media_detail():
    """시리즈 메타정보 수동 수정 및 표지 업로드"""
    db_type     = request.form.get('type', 'general')
    series_name  = request.form.get('series', '').strip()
    series_alias = request.form.get('series_alias', '').strip()
    author      = request.form.get('author', '').strip()
    isbn        = request.form.get('isbn', '').strip()
    publisher   = request.form.get('publisher', '').strip()
    summary     = request.form.get('summary', '').strip()
    link        = request.form.get('link', '').strip()
    genre       = request.form.get('genre', '').strip()
    tags        = request.form.get('tags', '').strip()
    cover_file  = request.files.get('cover_image')

    if not series_name:
        return jsonify({'success': False, 'error': _t('api.err_series_name_required')}), 400

    try:
        success, message = BookDetailService.update_media_detail(
            db_type=db_type,
            series_name=series_name,
            author=author,
            isbn=isbn,
            publisher=publisher,
            summary=summary,
            link=link,
            genre=genre,
            tags=tags,
            cover_file=cover_file,
            series_alias=series_alias
        )
        if success:
            try:
                from utils.redis_helper import redis_delete_pattern
                redis_delete_pattern(f"cache:history*:{db_type}:*")
                redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
            except Exception:
                pass
        return jsonify({'success': success, 'message': message if success else None, 'error': message if not success else None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/series/alias', methods=['POST', 'PATCH'])
@admin_required
def update_series_alias():
    """시리즈 전용 표시 별칭(series_alias) 수정 API"""
    data = request.get_json(silent=True) or request.form
    db_type      = data.get('type', 'general')
    series_name  = data.get('series', '').strip()
    series_alias = data.get('series_alias', '').strip()

    if not series_name:
        return jsonify({'success': False, 'error': _t('api.err_series_name_required')}), 400

    try:
        from repositories.book_repository import BookRepository
        BookRepository.update_series_alias(db_type, series_name, series_alias)
        try:
            from utils.redis_helper import redis_delete_pattern
            redis_delete_pattern(f"cache:history*:{db_type}:*")
            redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
        except Exception:
            pass
        return jsonify({'success': True, 'message': f'"{series_name}" 시리즈 별칭이 수정되었습니다.', 'series_alias': series_alias})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/books/<int:book_id>/alias', methods=['POST', 'PATCH'])
@admin_required
def update_book_alias(book_id):
    """단일 권수/도서 전용 표시 별칭(title_alias) 수정 API"""
    data = request.get_json(silent=True) or request.form
    db_type     = data.get('type', 'general')
    title_alias = data.get('title_alias', '').strip()

    try:
        from repositories.book_repository import BookRepository
        BookRepository.update_book_alias(db_type, book_id, title_alias)
        try:
            from utils.redis_helper import redis_delete_pattern
            redis_delete_pattern(f"cache:history*:{db_type}:*")
            redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
        except Exception:
            pass
        return jsonify({'success': True, 'message': f'도서(ID: {book_id}) 별칭이 수정되었습니다.', 'title_alias': title_alias})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/meta/recommend', methods=['GET'])
@login_required
def get_media_meta_recommend():
    """상세 설명이 비어있을 때, 유사한 시리즈 이름을 가진 메타데이터 추천"""
    db_type     = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    series_name = request.args.get('series', '')
    
    if not series_name:
        return jsonify({'success': False, 'error': _t('api.err_series_name_missing')}), 400
        
    try:
        recommends = MetadataService.get_meta_recommend(db_type, series_name)
        return jsonify({'success': True, 'recommends': recommends})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/meta/copy', methods=['POST'])
@admin_required
def copy_media_metadata():
    """추천받은 메타데이터(저자, 출판사, 줄거리 등)를 지정 도서 시리즈에 수동으로 복사 복원"""
    db_type       = request.form.get('type', 'general')
    target_series = request.form.get('target_series', '').strip()
    target_lib_id = request.form.get('target_library_id', '').strip()
    source_book_id = request.form.get('source_book_id', '').strip()
    
    if not target_series or not target_lib_id or not source_book_id:
        return jsonify({'success': False, 'error': _t('api.err_missing_params')}), 400
        
    try:
        success, message = MetadataService.copy_metadata(db_type, target_series, target_lib_id, source_book_id)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/next-book', methods=['GET'])
@login_required
def get_next_book_api():
    """시리즈 내 다음 도서 권 정보 조회 API"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    book_id = request.args.get('book_id')
    user_id = session.get('user_id', 1)
    
    if not book_id:
        return jsonify({'success': False, 'error': _t('api.err_book_id_missing')}), 400
        
    try:
        next_book = BookService.get_next_book(db_type, book_id, user_id=user_id)
        return jsonify({'success': True, 'next_book': next_book})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/books/<int:book_id>/info', methods=['GET'])
@login_required
def get_book_info(book_id):
    """단일 도서의 메타정보 조회 (Viewer에서 total_pages=0일 때 동적 계산용)"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    
    try:
        info = BookInfoService.get_viewer_info(db_type, book_id)
        if info is None:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        return jsonify({
            'success': True,
            'total_pages': info.get('total_pages', 0),
            'cover_image': info.get('cover_image')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/books/<int:book_id>/reader-info', methods=['GET'])
@login_required
def get_book_reader_info(book_id):
    """book_id만으로 openReader()를 즉시 호출할 수 있도록 제목/포맷/읽기 진척도를 반환 (킷오스크 모드 등 외부 딥링크용)"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    user_id = session.get('user_id')
    try:
        info = BookInfoService.get_reader_info(db_type, book_id, user_id=user_id)
        if info is None:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        return jsonify({'success': True, 'book': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/books/<int:book_id>/favorite', methods=['POST', 'PATCH'])
@login_required
def toggle_book_favorite(book_id):
    """특정 도서의 즐겨찾기 상태 변경"""
    db_type = request.form.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    try:
        is_favorite = int(request.form.get('is_favorite', 0))
    except ValueError:
        is_favorite = 0

    try:
        BookService.update_favorite(db_type, book_id, is_favorite, user_id=user_id)
        from services.series_service import SeriesService
        SeriesService.invalidate_all_books_cache()
        return jsonify({'success': True, 'message': _t('api.msg_favorite_updated')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/books/<int:book_id>/cover-align', methods=['POST', 'PATCH'])
@login_required
def update_book_cover_align(book_id):
    """도서 1권의 커버 썸네일 정렬(왼쪽/중앙/오른쪽) 변경 — 이중 페이지 스캔본 대응"""
    db_type = request.form.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    align = request.form.get('align', 'center').strip()

    try:
        updated = BookService.update_cover_align(db_type, book_id, align)
        if not updated:
            return jsonify({'success': False, 'error': f'해당 book_id={book_id}를 찾을 수 없습니다 (type={db_type}).'}), 404
        from services.series_service import SeriesService
        SeriesService.invalidate_all_books_cache()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/series/favorite', methods=['POST', 'PATCH'])
@login_required
def toggle_series_favorite_api():
    """특정 시리즈 전체의 즐겨찾기 상태 변경"""
    db_type = request.form.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    series_name = request.form.get('series_name', '').strip()
    try:
        is_favorite = int(request.form.get('is_favorite', 0))
    except ValueError:
        is_favorite = 0

    if not series_name:
        return jsonify({'success': False, 'error': 'series_name이 누락되었습니다.'}), 400

    try:
        BookService.update_series_favorite(db_type, series_name, is_favorite, user_id=user_id)
        from services.series_service import SeriesService
        SeriesService.invalidate_all_books_cache()
        return jsonify({'success': True, 'message': _t('api.msg_series_favorite_updated')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/author/favorite', methods=['POST', 'PATCH'])
@login_required
def toggle_author_favorite_api():
    """작가별 모음 카드 - 해당 작가(정규화 키)의 모든 작품 즐겨찾기 일괄 등록/해제"""
    db_type = request.form.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    author_key = request.form.get('author_key', '').strip()
    try:
        is_favorite = int(request.form.get('is_favorite', 0))
    except ValueError:
        is_favorite = 0

    if not author_key:
        return jsonify({'success': False, 'error': 'author_key가 누락되었습니다.'}), 400

    try:
        BookService.update_author_favorite(db_type, author_key, is_favorite, user_id=user_id)
        from services.series_service import SeriesService
        SeriesService.invalidate_all_books_cache()
        return jsonify({'success': True, 'message': _t('api.msg_series_favorite_updated')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/books/<int:book_id>/download', methods=['GET'])
@login_required
def download_book(book_id):
    """도서 파일을 다운로드합니다 (EPUB/PDF/TXT 전용 — iOS Books 앱 등 외부 앱 연동용)"""
    db_type = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    ALLOWED_FORMATS = ('epub', 'pdf', 'txt')

    try:
        from repositories.book_repository import BookRepository
        row = BookRepository.get_book_basic_info(db_type, book_id)

        if not row:
            return jsonify({'success': False, 'error': _t('api.err_book_not_found')}), 404

        file_path = row['file_path']
        file_format = (row['file_format'] or '').lower()

        if file_format not in ALLOWED_FORMATS:
            return jsonify({'success': False, 'error': '다운로드는 EPUB, PDF, TXT 포맷만 지원합니다.'}), 400

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': _t('api.err_file_not_found')}), 404

        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_map = {'epub': 'application/epub+zip', 'pdf': 'application/pdf', 'txt': 'text/plain'}
            mime_type = mime_map.get(file_format, 'application/octet-stream')

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mime_type
        )
    except Exception as e:
        import traceback
        print(f"[Download API] 오류:\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@book_routes_bp.route('/api/media/unlock-metadata', methods=['POST'])
@login_required
def unlock_media_metadata():
    """도서 및 시리즈 메타데이터 잠금 해제 (metadata_locked = 0)"""
    db_type = request.form.get('type', 'general')
    series_name = request.form.get('series_name')
    library_id = request.form.get('library_id')
    book_id = request.form.get('book_id')

    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    try:
        from repositories.book_repository import BookRepository
        success = BookRepository.unlock_media_metadata(
            db_type=db_type,
            series_name=series_name,
            library_id=library_id,
            book_id=book_id
        )
        if success:
            try:
                from utils.redis_helper import redis_delete_pattern
                redis_delete_pattern(f"cache:history*:{db_type}:*")
                redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
            except Exception:
                pass
            return jsonify({'success': True, 'message': '메타데이터 잠금이 해제되었습니다.'})
        else:
            return jsonify({'success': False, 'error': '해당 도서/시리즈를 찾을 수 없거나 이미 해제되었습니다.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
