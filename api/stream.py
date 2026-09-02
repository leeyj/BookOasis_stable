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
import hashlib

stream_bp = Blueprint('media_stream', __name__)


BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from services.cover_storage_service import get_covers_dir


def _seed_default_boss_key_image():
    """보스키(Alt+Q) 위장 화면 이미지를 covers/ 아래로 최초 1회 복사한다.
    covers/ 는 사용자 볼륨(git 비추적)이라, 이후 사용자가 같은 파일명으로
    직접 덮어쓰면 UI 없이도 위장 화면 이미지를 임의로 교체할 수 있다."""
    dest = os.path.join(get_covers_dir(), 'fake_screen.png')
    if os.path.exists(dest):
        return
    src = os.path.join(BASE_DIR, 'static', 'images', 'fake_screen.png')
    if not os.path.exists(src):
        return
    try:
        import shutil
        shutil.copyfile(src, dest)
    except Exception as e:
        print(f"[Boss-Key] Failed to seed default fake_screen.png: {e}")


_seed_default_boss_key_image()


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
    if key == 'video':
        return 'VIDEO'
    return 'TEXT'


def _build_landscape_video_fallback_svg(title, bg_start, bg_end, border, line, accent):
    lines = _split_title_lines(title, max_chars=13, max_lines=2)
    y_start = 214 if len(lines) == 1 else 196
    line_gap = 40
    lines_svg = ''.join(
        f'<text x="320" y="{y_start + i * line_gap}" text-anchor="middle" fill="#f8fafc" font-family="Noto Sans KR, Pretendard, sans-serif" font-size="32" font-weight="700">{_escape_xml(line)}</text>'
        for i, line in enumerate(lines)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360" role="img" aria-label="{_escape_xml(title)}">
  <defs><linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="{bg_start}" /><stop offset="100%" stop-color="{bg_end}" /></linearGradient></defs>
  <rect width="640" height="360" rx="18" fill="url(#bg)" />
  <polygon points="572,0 640,0 640,40" fill="{accent}" opacity="0.9" />
  <rect x="22" y="20" width="596" height="320" rx="12" fill="none" stroke="{border}" stroke-width="3" opacity="0.95" />
  <circle cx="320" cy="128" r="38" fill="none" stroke="{line}" stroke-width="3" opacity="0.92" />
  <polygon points="308,110 308,146 340,128" fill="{line}" opacity="0.95" />
  {lines_svg}
  <text x="320" y="308" text-anchor="middle" fill="#dbe3ea" font-family="monospace" font-size="22" letter-spacing="4" opacity="0.88">VIDEO</text>
</svg>'''


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
    label = _format_cover_label(file_format)

    # 영상 강좌 그리드는 CSS에서 16:9(object-fit: cover)로 표시되므로, 세로 420x600
    # 책 템플릿을 그대로 쓰면 위아래가 잘려나가 텅 빈 조각만 보인다 - 가로 전용 템플릿 사용
    if label == 'VIDEO':
        return _build_landscape_video_fallback_svg(title, bg_start, bg_end, border, line, accent)

    lines = _split_title_lines(title)
    y_start = 250 if len(lines) == 1 else 222 if len(lines) == 2 else 202
    line_gap = 48
    lines_svg = ''.join(
        f'<text x="210" y="{y_start + i * line_gap}" text-anchor="middle" fill="#f8fafc" font-family="Noto Sans KR, Pretendard, sans-serif" font-size="42" font-weight="700">{_escape_xml(line)}</text>'
        for i, line in enumerate(lines)
    )
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

@stream_bp.route('/api/media/epub/chapters', methods=['GET'])
@login_required
def get_epub_chapters_batch_api():
    """EPUB 여러 챕터를 한 번의 zip open으로 묶어서 반환 (뷰어 프리페치 전용).
    개별 챕터 엔드포인트를 프리페치 반경만큼 동시 호출하면 서버에서 같은 zip 파일을
    그만큼 반복해서 여는 문제가 있어, 반경 전체를 한 요청으로 묶기 위해 추가."""
    db_type = request.args.get('db_type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    user_id = session.get('user_id', 1)
    role = session.get('role')
    book_id = request.args.get('book_id')
    if not book_id:
        return jsonify({'error': _t('api.err_book_id_required')}), 400

    raw_indices = request.args.get('chapter_idx', '')
    try:
        indices = [int(x) for x in raw_indices.split(',') if x.strip() != '']
    except ValueError:
        return jsonify({'error': 'Invalid chapter_idx list'}), 400
    if not indices:
        return jsonify({'error': 'chapter_idx is required'}), 400

    # 프리페치 반경 기준으로 넉넉한 상한을 두어 과도한 배치 요청 남용을 방지
    MAX_BATCH_SIZE = 40
    if len(indices) > MAX_BATCH_SIZE:
        indices = indices[:MAX_BATCH_SIZE]

    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return jsonify({'error': _t('api.err_book_not_found')}), 404

    chapters, error = StreamService.get_epub_chapters_batch(file_path, book_id, db_type, indices)
    if error:
        return jsonify({'error': error}), 404 if error == 'File not found' else 500

    return jsonify({'success': True, 'chapters': chapters})

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

    data, mime, error = StreamService.extract_epub_resource(file_path, resource_path)
    if error:
        return jsonify({'error': error}), 404 if error == 'Resource not found' else 500

    res = Response(data, mimetype=mime or 'image/jpeg')
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

    covers_root = Path(get_covers_dir()).resolve()

    def _resolve_cover_path(name):
        # Prevent absolute-path override and path traversal outside covers directory.
        cleaned = str(name or '').lstrip('/\\')
        candidate = (covers_root / cleaned).resolve()
        try:
            candidate.relative_to(covers_root)
        except ValueError:
            return None
        return candidate

    decoded_filename = urllib.parse.unquote(filename)
    path = _resolve_cover_path(decoded_filename)
    if not path or not path.exists() or not path.is_file():
        # 만약 unquote 전 경로로 존재하는지 2차 체크 (Fallback)
        path_fallback = _resolve_cover_path(filename)
        if path_fallback and path_fallback.exists() and path_fallback.is_file():
            return send_cached_cover_file(path_fallback)
        return jsonify({'error': _t('api.err_cover_not_found')}), 404
    return send_cached_cover_file(path)


def send_cached_cover_file(path):
    """로컬 커버 파일을 ETag/Cache-Control(1일)과 함께 서빙 (304 빠른 반환 지원).
    /covers/<filename> 라우트뿐 아니라 오디오북/영상 강좌 포스터 캐시 서빙에도 공용으로 쓰인다."""
    import mimetypes
    path = Path(path)
    stat = path.stat()
    etag_source = f"{path}:{stat.st_mtime_ns}:{stat.st_size}"
    etag_val = hashlib.md5(etag_source.encode('utf-8')).hexdigest()[:16]
    if_none_match = request.headers.get('If-None-Match')
    if if_none_match and (if_none_match == etag_val or if_none_match == f'"{etag_val}"'):
        res = Response(status=304)
        res.headers['Cache-Control'] = 'public, max-age=86400'
        res.headers['ETag'] = f'"{etag_val}"'
        return res

    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or 'image/png'
    res = send_file(path, mimetype=mime, conditional=False)
    res.headers['Cache-Control'] = 'public, max-age=86400'
    res.headers['ETag'] = f'"{etag_val}"'
    return res



@stream_bp.route('/covers/fallback', methods=['GET'])
def get_fallback_cover_image():
    """커버 누락 시 제목 기반 SVG 커버를 동적으로 생성하여 반환"""
    title = (request.args.get('title') or 'Untitled').strip()
    file_format = (request.args.get('format') or 'text').strip()
    seed = (request.args.get('seed') or '').strip()

    svg = _build_fallback_svg(title, file_format, seed)
    res = Response(svg, mimetype='image/svg+xml')
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
        data = request.get_json(force=True, silent=True)
        if not data and request.data:
            try:
                import json as _json
                data = _json.loads(request.data.decode('utf-8'))
            except Exception:
                data = {}
        data = data or {}
        db_type = data.get('db_type', 'general')
        if not check_adult_permission(db_type):
            return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
        book_id = data.get('book_id')
        page_idx = data.get('page_idx') # 0-indexed로 처리
        total_pages = data.get('total_pages')
        epub_session = data.get('epub_session') or None
        flush_immediately = bool(data.get('flush_immediately', False))
        user_id = session.get('user_id', 1)

        if book_id is None or page_idx is None:
            return jsonify({'success': False, 'error': _t('api.err_book_id_page_idx_required')}), 400

        # total_pages가 제공되지 않은 경우 기본값으로 1을 지정하거나 처리
        if total_pages is None:
            total_pages = 1

        persisted = StreamService.record_progress(
            db_type,
            book_id,
            page_idx,
            total_pages,
            user_id=user_id,
            epub_session=epub_session,
            flush_immediately=flush_immediately,
        )
        if flush_immediately and not persisted:
            return jsonify({'success': False, 'error': 'progress persistence is busy'}), 503
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
        scope = data.get('scope', 'book')
        series_name = str(data.get('series_name') or '').strip()
        library_id = data.get('library_id')
        user_id = session.get('user_id', 1)

        if book_id is None:
            return jsonify({'success': False, 'error': 'book_id가 누락되었습니다.'}), 400
        if scope not in ('book', 'series'):
            return jsonify({'success': False, 'error': '지원하지 않는 읽지 않음 범위입니다.'}), 400
        if scope == 'series' and (not series_name or library_id is None):
            return jsonify({'success': False, 'error': '시리즈명 또는 라이브러리 ID가 누락되었습니다.'}), 400

        affected_count = ReadingProgressService.mark_unread(
            db_type,
            book_id,
            user_id=user_id,
            series_name=series_name if scope == 'series' else None,
            library_id=library_id if scope == 'series' else None,
        )
        return jsonify({'success': True, 'affected_count': affected_count, 'scope': scope})
    except Exception as e:
        print(f"[Unread API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@stream_bp.route('/api/media/series/complete', methods=['POST'])
@login_required
def mark_series_as_completed():
    """시리즈의 도서들을 현재 사용자 기준 일괄 완독 처리"""
    try:
        data = request.get_json(silent=True) or {}
        db_type = data.get('db_type', 'general')
        if not check_adult_permission(db_type):
            return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

        user_id = session.get('user_id', 1)

        if db_type == 'audiobook':
            raw_audiobook_id = data.get('audiobook_id')
            raw_track_ids = data.get('track_ids') or []

            try:
                audiobook_id = int(raw_audiobook_id)
            except Exception:
                audiobook_id = 0

            if audiobook_id <= 0:
                return jsonify({'success': False, 'error': 'audiobook_id가 누락되었습니다.'}), 400

            updated_count = ReadingProgressService.mark_audiobook_completed(
                audiobook_id,
                user_id=user_id,
                track_ids=raw_track_ids if isinstance(raw_track_ids, list) else [],
            )
        else:
            raw_book_ids = data.get('book_ids') or []
            if not isinstance(raw_book_ids, list) or len(raw_book_ids) == 0:
                return jsonify({'success': False, 'error': 'book_ids가 누락되었습니다.'}), 400

            updated_count = ReadingProgressService.mark_books_completed(db_type, raw_book_ids, user_id=user_id)

        return jsonify({'success': True, 'updated_count': int(updated_count)})
    except Exception as e:
        print(f"[Series Complete API Error] {e}")
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

