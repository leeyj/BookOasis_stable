# -*- coding: utf-8 -*-
"""
stream.py – 만화/TXT/PDF 스트리밍 및 커버 이미지 서빙 라우터 (Controller Layer)
"""
import os
import re
import mimetypes
from flask import Blueprint, request, Response, jsonify, send_file, session
from services.stream_service import StreamService, get_img_files
from utils.cache_helper import get_zip_file_hybrid
from api.auth import login_required, check_adult_permission, admin_required
from utils.i18n import _t
import database

stream_bp = Blueprint('media_stream', __name__)

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COVERS_DIR = os.path.join(BASE_DIR, 'covers')

@stream_bp.route('/api/media/stream', methods=['GET'])
@login_required
def stream_comic_page():
    """만화책 ZIP/CBZ 실시간 이미지 추출 (RAM 캐시 + Prefetch 적용)"""
    db_type  = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    book_id  = request.args.get('book_id')
    page_idx = int(request.args.get('page_idx', 0))
    user_id  = session.get('user_id', 1)

    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    try:
        book_id = int(book_id)
    except (ValueError, TypeError):
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    result = StreamService.extract_page(file_path, page_idx, db_type=db_type, book_id=book_id)
    if result is None:
        return jsonify({'error': _t('api.err_extract_page')}), 400

    img_data, mime_type = result

    # 진행도 기록
    try:
        zf = get_zip_file_hybrid(file_path)
        if zf:
            StreamService.record_progress(db_type, book_id, page_idx, len(get_img_files(file_path, zf)), user_id=user_id)
    except Exception as e:
        print(f"[Progress Recorder] Fail: {e}")

    res = Response(img_data, mimetype=mime_type)
    res.headers['Cache-Control'] = 'public, max-age=31536000'
    return res

@stream_bp.route('/api/media/txt', methods=['GET'])
@login_required
def get_txt_content():
    """소설·TXT 파일 UTF-8 서빙 (CP949/EUC-KR 자동 변환)"""
    db_type = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    content, error = StreamService.get_txt_content(file_path)
    if error:
        return jsonify({'error': error}), 404 if error == 'File not found' else 500

    return Response(content, mimetype='text/plain; charset=utf-8')

@stream_bp.route('/api/media/pdf', methods=['GET'])
@login_required
def get_pdf_range():
    """대용량 PDF HTTP Range Requests 지원"""
    db_type = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    if not os.path.exists(file_path):
        return jsonify({'error': _t('api.err_file_not_found')}), 404

    # 파일 확장자에 맞는 mime-type 결정 (OS별 mimetypes 모듈 누락 대비 하드코딩 매핑 우선 적용)
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext == '.epub':
        mime = 'application/epub+zip'
    elif ext == '.pdf':
        mime = 'application/pdf'
    elif ext == '.txt':
        mime = 'text/plain'
    else:
        mime, _ = mimetypes.guess_type(file_path)
        mime = mime or 'application/octet-stream'

    range_header = request.headers.get('Range')
    if not range_header:
        return send_file(file_path, mimetype=mime)

    size = os.path.getsize(file_path)
    byte1, byte2 = 0, None
    m = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if m:
        byte1 = int(m.group(1))
        if m.group(2):
            byte2 = int(m.group(2))
    if byte2 is None:
        byte2 = size - 1
    length = byte2 - byte1 + 1

    try:
        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)
        rv = Response(data, 206, mimetype=mime, direct_passthrough=True)
        rv.headers['Content-Range'] = f'bytes {byte1}-{byte2}/{size}'
        rv.headers['Accept-Ranges'] = 'bytes'
        rv.headers['Content-Length'] = str(length)
        return rv
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@stream_bp.route('/covers/<path:filename>', methods=['GET'])
def get_cover_image(filename):
    """복원된 정적 표지 이미지 서빙 (더블 인코딩 방어용 unquote 적용, 하위 디렉토리 지원)"""
    import urllib.parse
    decoded_filename = urllib.parse.unquote(filename)
    path = os.path.join(COVERS_DIR, decoded_filename)
    if not os.path.exists(path):
        # 만약 unquote 전 경로로 존재하는지 2차 체크 (Fallback)
        path_fallback = os.path.join(COVERS_DIR, filename)
        if os.path.exists(path_fallback):
            return send_file(path_fallback, mimetype='image/png')
        return jsonify({'error': _t('api.err_cover_not_found')}), 404
    return send_file(path, mimetype='image/png')

@stream_bp.route('/api/media/cache/stats', methods=['GET'])
@admin_required
def cache_stats():
    """RAM 캐시 사용량 모니터링"""
    from api.cache import image_cache, zip_cache, namelist_cache
    return jsonify({
        'success'              : True,
        'image_cache'          : image_cache.stats(),
        'zip_cache_count'      : len(zip_cache.cache),
        'namelist_cache_count' : len(namelist_cache.cache),
    })

@stream_bp.route('/api/media/fonts', methods=['GET'])
@login_required
def list_custom_fonts():
    """사용자 정의 폰트 디렉터리 스캔 및 목록 조회"""
    custom_fonts_dir = os.path.join(BASE_DIR, 'static', 'fonts', 'custom')
    if not os.path.exists(custom_fonts_dir):
        try:
            os.makedirs(custom_fonts_dir, exist_ok=True)
        except Exception as e:
            print(f"[Fonts API] Failed to create directory: {e}")
    
    fonts = []
    allowed_exts = {'.woff2', '.woff', '.ttf', '.otf'}
    if os.path.exists(custom_fonts_dir):
        for f in os.listdir(custom_fonts_dir):
            name, ext = os.path.splitext(f)
            if ext.lower() in allowed_exts:
                fonts.append({
                    'name': name,
                    'filename': f,
                    'url': f'/static/fonts/custom/{f}'
                })
    return jsonify({
        'success': True,
        'fonts': fonts
    })

@stream_bp.route('/api/media/progress', methods=['POST'])
@login_required
def save_viewer_progress():
    """만화, TXT, EPUB, PDF 공통 독서 진행률 API 기록 엔드포인트"""
    try:
        data = request.json or {}
        db_type = data.get('db_type', 'general')
        if not check_adult_permission(db_type):
            return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
        book_id = data.get('book_id')
        page_idx = data.get('page_idx') # 0-indexed로 처리
        total_pages = data.get('total_pages')
        user_id = session.get('user_id', 1)

        if book_id is None or page_idx is None:
            return jsonify({'success': False, 'error': _t('api.err_book_id_page_idx_required')}), 400

        # total_pages가 제공되지 않은 경우 기본값으로 1을 지정하거나 처리
        if total_pages is None:
            total_pages = 1

        StreamService.record_progress(db_type, book_id, page_idx, total_pages, user_id=user_id)
        return jsonify({'success': True})
    except Exception as e:
        print(f"[Progress API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@stream_bp.route('/api/media/unread', methods=['POST'])
@login_required
def mark_book_as_unread():
    """도서를 읽지 않은 상태로 변경 (user_progress 및 user_reading_log 기록 제거)"""
    try:
        data = request.json or {}
        db_type = data.get('db_type', 'general')
        if not check_adult_permission(db_type):
            return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
        book_id = data.get('book_id')
        user_id = session.get('user_id', 1)

        if book_id is None:
            return jsonify({'success': False, 'error': 'book_id가 누락되었습니다.'}), 400

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        # user_progress 및 user_reading_log 내역 삭제
        cursor.execute("DELETE FROM user_progress WHERE book_id = ? AND user_id = ?", (book_id, user_id))
        cursor.execute("DELETE FROM user_reading_log WHERE book_id = ? AND user_id = ?", (book_id, user_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"[Unread API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@stream_bp.route('/api/media/preload-next-book', methods=['POST'])
@login_required
def preload_next_book_api():
    """다음 권 도서 백그라운드 선제 다운로드 및 캐싱 API"""
    try:
        data = request.json or {}
        db_type = data.get('db_type', 'general')
        if not check_adult_permission(db_type):
            return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
        book_id = data.get('book_id')
        user_id = session.get('user_id', 1)

        if not book_id:
            return jsonify({'success': False, 'error': _t('api.err_book_id_required')}), 400

        from services.book_service import BookService
        from utils.cache_helper import start_background_copy

        # 1. 다음 권 조회
        next_book = BookService.get_next_book(db_type, book_id, user_id=user_id)
        if not next_book or not next_book.get('file_path'):
            return jsonify({'success': True, 'message': _t('api.msg_no_next_book')})

        # 2. 백그라운드 복사 태스크 기동
        next_file_path = next_book['file_path']
        if os.path.exists(next_file_path):
            start_background_copy(next_file_path)
            print(f"[Viewer-Preload] Preloading next book successfully: {next_book['title']}")
            return jsonify({'success': True, 'preloaded_book_id': next_book['id']})
        else:
            return jsonify({'success': False, 'error': _t('api.err_next_book_not_exist')}), 404

    except Exception as e:
        print(f"[Preload API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

