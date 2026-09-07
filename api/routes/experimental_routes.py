# -*- coding: utf-8 -*-
"""
experimental_routes.py - 기존 뷰어 로직과 완전히 분리된 실험적 기능 테스트 라우터.
여기 추가되는 화면들은 프로덕션 뷰어 코드를 전혀 건드리지 않고,
기존 읽기 전용 API(/api/media/stream, /api/media/books/<id>/info)만 재사용한다.
"""
import os
from flask import Blueprint, render_template, request, jsonify, Response
from api.auth import login_required

experimental_bp = Blueprint('experimental', __name__)


@experimental_bp.route('/experimental/page-turn', methods=['GET'])
@login_required
def page_turn_test():
    """이미지 기반(zip/cbz) 도서 대상 실제 페이지 넘김 애니메이션 실험 페이지."""
    return render_template('experimental_page_turn.html')


# Paged.js 기반 TXT/EPUB 페이지네이션 스파이크 테스트.
# 목적: "흘러가는 EPUB 본문을 실측 기반으로 분리된 페이지 DOM으로 잘라낼 수 있는가"를
# 실제 성능 숫자로 판단하기 위함 - 판단 전까지는 프로덕션 코드에 절대 반영하지 않는다.
# 라이브러리는 MIT 라이선스 Paged.js(static/lib/paged.polyfill.js, v0.4.3 vendoring).
_TEST_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'test'
)
# 웹소설(텍스트 위주) + 실제 홈서버 EPUB 크기 분포 극단값 벤치마크(최대/평균 근접) 두 세트.
PAGEDJS_TEST_SUBDIRS = ['화산파 천재검귀', 'epub_size_bench']


def _resolve_test_epub_path(file_id):
    """디렉토리 탈출(../) 방지 - "<서브디렉토리>/<파일명>" 형식만 받아 허용된 테스트
    디렉토리 목록(PAGEDJS_TEST_SUBDIRS) 하위로만 고정시킨다."""
    file_id = (file_id or '').replace('\\', '/')
    if '/' not in file_id:
        return None
    subdir, filename = file_id.split('/', 1)
    safe_name = os.path.basename(filename)
    if subdir not in PAGEDJS_TEST_SUBDIRS or not safe_name:
        return None
    base_dir = os.path.abspath(os.path.join(_TEST_ROOT, subdir))
    full_path = os.path.abspath(os.path.join(base_dir, safe_name))
    if not (full_path == base_dir or full_path.startswith(base_dir + os.sep)):
        return None
    return full_path


@experimental_bp.route('/experimental/pagedjs-test', methods=['GET'])
@login_required
def pagedjs_test():
    """Paged.js 기반 EPUB 페이지네이션 성능 실측 테스트 페이지."""
    return render_template('experimental_pagedjs_test.html')


@experimental_bp.route('/experimental/pagedjs-test/api/files', methods=['GET'])
@login_required
def pagedjs_test_files():
    """테스트 디렉토리들(PAGEDJS_TEST_SUBDIRS)의 EPUB 파일 목록 - id는 "서브디렉토리/파일명"."""
    try:
        entries = []
        for subdir in PAGEDJS_TEST_SUBDIRS:
            dir_path = os.path.join(_TEST_ROOT, subdir)
            if not os.path.isdir(dir_path):
                continue
            for f in sorted(os.listdir(dir_path)):
                if not f.lower().endswith('.epub'):
                    continue
                size_mb = round(os.path.getsize(os.path.join(dir_path, f)) / 1024 / 1024, 1)
                entries.append({
                    'id': subdir + '/' + f,
                    'label': subdir + ' / ' + f + f' ({size_mb}MB)',
                })
        return jsonify({'success': True, 'files': entries})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@experimental_bp.route('/experimental/pagedjs-test/api/meta', methods=['GET'])
@login_required
def pagedjs_test_meta():
    """선택한 테스트 EPUB의 메타데이터(제목, 챕터 수, TOC) 조회.
    book_id를 넘기지 않아 Redis 캐시를 타지 않는다 - 스파이크 테스트라 매번 새로 파싱해도
    무방하고, 실제 서비스 캐시 네임스페이스를 오염시키지 않기 위함."""
    filename = request.args.get('file', '')
    file_path = _resolve_test_epub_path(filename)
    if not file_path or not os.path.exists(file_path):
        return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다'}), 404

    from services.text_epub_content_service import TextEpubContentService
    meta, err = TextEpubContentService.get_epub_meta(file_path, None, 'pagedjs_test')
    if err:
        return jsonify({'success': False, 'error': err}), 400
    return jsonify({'success': True, 'meta': meta})


@experimental_bp.route('/experimental/pagedjs-test/api/chapter', methods=['GET'])
@login_required
def pagedjs_test_chapter():
    """선택한 테스트 EPUB의 챕터 1개 HTML 본문 조회."""
    filename = request.args.get('file', '')
    chapter_idx = request.args.get('idx', '0')
    file_path = _resolve_test_epub_path(filename)
    if not file_path or not os.path.exists(file_path):
        return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다'}), 404

    from services.text_epub_content_service import TextEpubContentService
    result, err = TextEpubContentService.get_epub_chapter(file_path, None, 'pagedjs_test', chapter_idx)
    if err:
        return jsonify({'success': False, 'error': err}), 400
    return jsonify({'success': True, 'chapter': result})


@experimental_bp.route('/experimental/pagedjs-test/api/epub-image', methods=['GET'])
@login_required
def pagedjs_test_epub_image():
    """선택한 테스트 EPUB 내부의 이미지 리소스 서빙.

    챕터 HTML은 book_id 기반 프로덕션 엔드포인트(/api/media/epub-image)를 가리키는
    <img> 태그를 그대로 담고 있는데, 이 테스트 파일들은 DB에 등록된 book이 아니라서
    book_id가 없다(그래서 여태 이미지가 깨져 보였다 - 실제 이미지 로딩 비용이 측정에서
    빠져 있던 원인). 프론트에서 그 src를 이 엔드포인트로 치환해 실제 이미지가 뜨게 한다."""
    filename = request.args.get('file', '')
    resource_path = request.args.get('path', '')
    file_path = _resolve_test_epub_path(filename)
    if not file_path or not os.path.exists(file_path) or not resource_path:
        return jsonify({'success': False, 'error': '이미지를 찾을 수 없습니다'}), 404

    from services.stream_service import StreamService
    data, mime, error = StreamService.extract_epub_resource(file_path, resource_path)
    if error:
        return jsonify({'success': False, 'error': error}), 404 if error == 'Resource not found' else 500

    res = Response(data, mimetype=mime or 'image/jpeg')
    res.headers['Cache-Control'] = 'public, max-age=31536000'
    return res
