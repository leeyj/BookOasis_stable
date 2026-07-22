# -*- coding: utf-8 -*-
"""
stream.py – 만화/TXT/PDF 스트리밍 및 커버 이미지 서빙 라우터 (Controller Layer)
"""
import os
import re
import mimetypes
import urllib.parse
from pathlib import Path
from flask import Blueprint, request, Response, jsonify, send_file, session
from services.reading_progress_service import ReadingProgressService
from services.stream_service import StreamService
from api.auth import login_required, check_adult_permission, admin_required
from utils.safe_file_response import stream_file_safely
from utils.i18n import _t
import database

stream_bp = Blueprint('media_stream', __name__)

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COVERS_DIR = os.path.join(BASE_DIR, 'covers')


def _hash_string(value):
    text = str(value or '')
    h = 2166136261
    for ch in text:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _escape_xml(value):
    return str(value or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')


def _split_title_lines(title, max_chars=9, max_lines=3):
    chars = list(str(title or '').strip() or 'Untitled')
    lines = []
    idx = 0
    while idx < len(chars) and len(lines) < max_lines:
        lines.append(''.join(chars[idx:idx + max_chars]))
        idx += max_chars
    if idx < len(chars) and lines:
        last = lines[-1]
        lines[-1] = f"{last[:-1]}…" if len(last) > 1 else '…'
    return lines


def _format_cover_label(file_format):
    key = str(file_format or 'text').lower()
    if key in ('zip', 'cbz', 'comic'):
        return 'COMIC'
    if key in ('imgdir', 'img'):
        return 'IMG'
    if key == 'epub':
        return 'EPUB'
    if key == 'pdf':
        return 'PDF'
    if key in ('audiobook', 'audio'):
        return 'AUDIO'
    return 'TEXT'


def _build_fallback_svg(title, file_format='text', seed=''):
    themes = [
        ('#13253a', '#0b1828', '#79c2ff', '#a7dcff', '#82d9b1'),
        ('#2b1f3a', '#15142a', '#b79bff', '#cab9ff', '#ffd06e'),
        ('#3a231e', '#1f1516', '#ffaf8f', '#ffc5ab', '#ffd66e'),
        ('#1b2f3a', '#101924', '#8dd3ff', '#b7e6ff', '#f8d878'),
        ('#3a311d', '#1f1a12', '#dfc37e', '#f1dcab', '#8cd0ff'),
        ('#22263a', '#121625', '#9ea8ff', '#c0c7ff', '#a4e3b0'),
    ]
    ref = seed or title or 'Untitled'
    h = _hash_string(ref)
    bg_start, bg_end, border, line, accent = themes[h % len(themes)]
    lines = _split_title_lines(title)
    y_start = 250 if len(lines) == 1 else 222 if len(lines) == 2 else 202
    line_gap = 48
    lines_svg = ''.join(
        f'<text x="210" y="{y_start + i * line_gap}" text-anchor="middle" fill="#f8fafc" font-family="Noto Sans KR, Pretendard, sans-serif" font-size="42" font-weight="700">{_escape_xml(line)}</text>'
        for i, line in enumerate(lines)
    )
    label = _format_cover_label(file_format)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="420" height="600" viewBox="0 0 420 600" role="img" aria-label="{_escape_xml(title)}">
  <defs><linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="{bg_start}" /><stop offset="100%" stop-color="{bg_end}" /></linearGradient></defs>
  <rect width="420" height="600" rx="20" fill="url(#bg)" />
  <polygon points="366,0 420,0 420,54" fill="{accent}" opacity="0.9" />
  <rect x="28" y="22" width="364" height="556" rx="14" fill="none" stroke="{border}" stroke-width="3.2" opacity="0.95" />
  <rect x="48" y="52" width="324" height="4" rx="2" fill="{line}" opacity="0.92" />
  {lines_svg}
  <text x="210" y="500" text-anchor="middle" fill="#dbe3ea" font-family="monospace" font-size="28" letter-spacing="4" opacity="0.88">{label}</text>
</svg>'''

@stream_bp.route('/api/media/stream', methods=['GET'])
@login_required
def stream_comic_page():
    """만화책 ZIP/CBZ 실시간 이미지 추출 (RAM 캐시 + Prefetch 적용, 읽기 전용)"""
    db_type  = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id  = session.get('user_id', 1)
    role     = session.get('role')
    book_id  = request.args.get('book_id')
    page_idx = int(request.args.get('page_idx', 0))

    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    try:
        book_id = int(book_id)
    except (ValueError, TypeError):
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path, file_format = StreamService.get_book_file_info(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    result = StreamService.extract_page(file_path, page_idx, db_type=db_type, book_id=book_id)
    if result is None:
        return jsonify({'error': _t('api.err_extract_page')}), 400

    img_data, mime_type = result

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
    user_id = session.get('user_id', 1)
    role = session.get('role')
    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    content, error = StreamService.get_txt_content(file_path)
    if error:
        return jsonify({'error': error}), 404 if error == 'File not found' else 500

    return Response(content, mimetype='text/plain; charset=utf-8')

@stream_bp.route('/api/media/epub', methods=['GET'])
@login_required
def get_epub_content():
    """EPUB 파일 파싱 후 정제된 텍스트/HTML 반환"""
    db_type = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    role = session.get('role')
    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    data, error = StreamService.get_epub_content(file_path, book_id, db_type)
    if error:
        return jsonify({'error': error}), 404 if error == 'File not found' else 500

    return jsonify(data)

@stream_bp.route('/api/media/epub/meta', methods=['GET'])
@login_required
def get_epub_meta_api():
    """EPUB 초고속 메타데이터(제목, TOC 목차, total_chapters) 반환"""
    db_type = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    role = session.get('role')
    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    data, error = StreamService.get_epub_meta(file_path, book_id, db_type)
    if error:
        return jsonify({'error': error}), 404 if error == 'File not found' else 500

    return jsonify(data)

@stream_bp.route('/api/media/epub/chapter', methods=['GET'])
@login_required
def get_epub_chapter_api():
    """EPUB 단일 챕터(chapter_idx) 텍스트/HTML 전용 스트리밍 반환"""
    db_type = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    role = session.get('role')
    book_id = request.args.get('book_id')
    chapter_idx = request.args.get('chapter_idx', 0)
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    data, error = StreamService.get_epub_chapter(file_path, book_id, db_type, chapter_idx)
    if error:
        return jsonify({'error': error}), 404 if error == 'File not found' else 500

    return jsonify(data)

@stream_bp.route('/api/media/epub-image', methods=['GET'])
@login_required
def get_epub_image():
    """EPUB 파일 내부의 특정 이미지 서빙"""
    db_type = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    role = session.get('role')
    book_id = request.args.get('book_id')
    resource_path = request.args.get('path')
    if not book_id or not resource_path:
        return jsonify({'error': 'book_id and path are required'}), 400

    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    data, error = StreamService.extract_epub_resource(file_path, resource_path)
    if error:
        return jsonify({'error': error}), 404 if error == 'Resource not found' else 500

    mime, _ = mimetypes.guess_type(resource_path)
    mime = mime or 'image/jpeg'

    res = Response(data, mimetype=mime)
    res.headers['Cache-Control'] = 'public, max-age=31536000'
    return res

@stream_bp.route('/api/media/pdf', methods=['GET'])
@login_required
def get_pdf_range():
    """대용량 PDF HTTP Range Requests 지원"""
    db_type = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    role = session.get('role')
    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
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
        try:
            return stream_file_safely(file_path, mimetype=mime)
        except OSError as e:
            return jsonify({'error': str(e)}), 500

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
    import mimetypes

    covers_root = Path(COVERS_DIR).resolve()

    def _resolve_cover_path(name):
        # Prevent absolute-path override and path traversal outside covers directory.
        cleaned = str(name or '').lstrip('/\\')
        candidate = (covers_root / cleaned).resolve()
        try:
            candidate.relative_to(covers_root)
        except ValueError:
            return None
        return candidate

    def _send_cover(path):
        mime, _ = mimetypes.guess_type(path)
        mime = mime or 'image/png'
        res = send_file(path, mimetype=mime, conditional=True, etag=True)
        # Covers are mostly immutable between scans; cache to reduce dashboard refresh flicker/network.
        res.headers['Cache-Control'] = 'public, max-age=86400'
        return res

    decoded_filename = urllib.parse.unquote(filename)
    path = _resolve_cover_path(decoded_filename)
    if not path or not path.exists() or not path.is_file():
        # 만약 unquote 전 경로로 존재하는지 2차 체크 (Fallback)
        path_fallback = _resolve_cover_path(filename)
        if path_fallback and path_fallback.exists() and path_fallback.is_file():
            return _send_cover(path_fallback)
        return jsonify({'error': _t('api.err_cover_not_found')}), 404
    return _send_cover(path)


@stream_bp.route('/covers/fallback', methods=['GET'])
def get_fallback_cover_image():
    """커버 누락 시 제목 기반 SVG 커버를 동적으로 생성하여 반환"""
    title = (request.args.get('title') or 'Untitled').strip()
    file_format = (request.args.get('format') or 'text').strip()
    seed = (request.args.get('seed') or '').strip()

    svg = _build_fallback_svg(title, file_format, seed)
    res = Response(svg, mimetype='image/svg+xml')
    # 제목/포맷 기반 생성 이미지이므로 강한 캐시 허용
    res.headers['Cache-Control'] = 'public, max-age=86400'
    res.set_etag(str(_hash_string(f"{title}|{file_format}|{seed}")))
    return res

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
        epub_session = data.get('epub_session') or None
        user_id = session.get('user_id', 1)

        if book_id is None or page_idx is None:
            return jsonify({'success': False, 'error': _t('api.err_book_id_page_idx_required')}), 400

        # total_pages가 제공되지 않은 경우 기본값으로 1을 지정하거나 처리
        if total_pages is None:
            total_pages = 1

        StreamService.record_progress(
            db_type,
            book_id,
            page_idx,
            total_pages,
            user_id=user_id,
            epub_session=epub_session
        )
        return jsonify({'success': True})
    except Exception as e:
        print(f"[Progress API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@stream_bp.route('/api/media/progress-state', methods=['GET'])
@login_required
def get_viewer_progress_state():
    """도서별 진행률/세션 포인터 조회 (크로스 디바이스 이어읽기 복원용)"""
    try:
        db_type = request.args.get('db_type', 'general')
        if not check_adult_permission(db_type):
            return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

        book_id = request.args.get('book_id')
        if not book_id:
            return jsonify({'success': False, 'error': _t('api.err_book_id_required')}), 400

        user_id = session.get('user_id', 1)
        state = StreamService.get_progress_state(db_type, book_id, user_id=user_id)
        if not state:
            return jsonify({'success': False, 'error': 'book not found'}), 404

        return jsonify({'success': True, 'state': state})
    except Exception as e:
        print(f"[Progress State API Error] {e}")
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

        ReadingProgressService.mark_unread(db_type, book_id, user_id=user_id)
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

