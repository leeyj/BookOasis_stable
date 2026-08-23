# -*- coding: utf-8 -*-
"""
gdrive_view_copy_routes.py – 구글 드라이브 "책 단위 사전복사(뷰어)" 기능을 플러그인이
조회/제어할 수 있게 여는 API 라우터.

기존 gdrive_copy_routes.py(카테고리와 무관한 "Drive에서 복사해오기" 일괄 복사)와는
별개 기능이다 — 이쪽은 services/gdrive_view_copy_service.py가 책을 열 때마다 그
1권만 자동으로 복사하는 흐름을 다룬다. 지금까지는 뷰어 스트림 경로 안에서만 호출돼
플러그인이 상태를 조회하거나(뷰어를 열지 않고) 미리 복사를 트리거할 방법이 없었다.

실험적 기능이라 다른 gdrive API와 동일하게 DEVELOP=true + admin_required로 가드한다.
"""
import os
from flask import Blueprint, request, jsonify
from api.auth import admin_required

gdrive_view_copy_bp = Blueprint('gdrive_view_copy', __name__)


def _develop_mode_enabled():
    return os.environ.get('DEVELOP', 'false').lower() == 'true'


def _normalize_db_type(value):
    db_type = str(value or 'general').strip().lower()
    if db_type not in ('general', 'adult', 'audiobook', 'video'):
        return None
    return db_type


@gdrive_view_copy_bp.route('/api/gdrive-view-copy/libraries', methods=['GET'])
@admin_required
def list_gdrive_view_copy_libraries():
    """gdrive 공유 링크가 포함된 카테고리 목록과, 각 카테고리의 뷰-복사 연결 설정
    (리모트/마운트 루트, 설정 완료 여부)을 반환한다. 플러그인이 "어느 카테고리가
    사전복사 대상인지"를 스스로 조회할 수 있게 하기 위한 메타 조회 API다."""
    if not _develop_mode_enabled():
        return jsonify({'success': False, 'error': '지원하지 않는 기능입니다.'}), 404

    db_type = _normalize_db_type(request.args.get('type'))
    if not db_type:
        return jsonify({'success': False, 'error': '알 수 없는 db_type 입니다.'}), 400

    try:
        from services.category_service import CategoryService
        from utils.drive_helper import has_gdrive_share_line

        libraries = CategoryService.get_libraries(db_type)
        items = []
        for lib in libraries:
            if not has_gdrive_share_line(lib.get('physical_path')):
                continue
            remote = lib.get('gdrive_copy_remote') or ''
            mirror_path = lib.get('gdrive_view_local_mirror_path') or ''
            items.append({
                'id': lib['id'],
                'name': lib['name'],
                'gdrive_copy_remote': remote,
                'gdrive_view_local_mirror_path': mirror_path,
                'configured': bool(remote and mirror_path),
            })
        return jsonify({'success': True, 'type': db_type, 'libraries': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@gdrive_view_copy_bp.route('/api/gdrive-view-copy/status', methods=['GET'])
@admin_required
def get_gdrive_view_copy_status():
    """책 한 권의 뷰-복사 상태를 뷰어를 열지 않고 조회한다. 실제 복사를 트리거하지
    않는 순수 조회 전용 엔드포인트 — 복사를 시키려면 /prefetch를 쓴다."""
    if not _develop_mode_enabled():
        return jsonify({'success': False, 'error': '지원하지 않는 기능입니다.'}), 404

    db_type = _normalize_db_type(request.args.get('type'))
    if not db_type:
        return jsonify({'success': False, 'error': '알 수 없는 db_type 입니다.'}), 400

    try:
        book_id = int(request.args.get('book_id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'book_id가 올바르지 않습니다.'}), 400

    try:
        result = _lookup_gdrive_view_copy_status(db_type, book_id)
        if result is None:
            return jsonify({'success': False, 'error': '도서를 찾을 수 없습니다.'}), 404
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@gdrive_view_copy_bp.route('/api/gdrive-view-copy/prefetch', methods=['POST'])
@admin_required
def prefetch_gdrive_view_copy():
    """책 한 권을 뷰어로 열지 않고도 미리 복사해둔다 — 코어의 resolve_viewable_path()를
    그대로 재사용하므로(락/TTL/미지원 판정 등 기존 규칙 전부 동일하게 적용), 예를 들어
    "이 카테고리 전체를 여행 전에 미리 당겨두기" 같은 플러그인을 만들 수 있다.
    동기 호출이며(내부에서 최대 수 초의 VFS 가시성 폴링 포함), 여러 권을 한 번에
    미리 복사하려는 플러그인은 이 엔드포인트를 book_id별로 순차 호출해야 한다."""
    if not _develop_mode_enabled():
        return jsonify({'success': False, 'error': '지원하지 않는 기능입니다.'}), 404

    data = request.get_json(silent=True) or {}
    db_type = _normalize_db_type(data.get('type'))
    if not db_type:
        return jsonify({'success': False, 'error': '알 수 없는 db_type 입니다.'}), 400

    try:
        book_id = int(data.get('book_id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'book_id가 올바르지 않습니다.'}), 400

    try:
        from repositories.book_repository import BookRepository
        from repositories.category_repository import CategoryRepository
        from services.gdrive_view_copy_service import resolve_viewable_path
        from utils.drive_helper import is_gdrive_url

        row = BookRepository.get_book_file_path_with_permission(db_type, book_id, '', [])
        if not row:
            return jsonify({'success': False, 'error': '도서를 찾을 수 없습니다.'}), 404

        file_path = row['file_path']
        if not is_gdrive_url(file_path):
            return jsonify({'success': True, 'triggered': False, 'reason': 'not_a_gdrive_book'})

        library = CategoryRepository.get_library_by_id(db_type, row.get('library_id'))
        resolved_path = resolve_viewable_path(db_type, book_id, file_path, library)

        status_result = _lookup_gdrive_view_copy_status(db_type, book_id) or {}
        return jsonify({
            'success': True,
            'triggered': True,
            'resolved_locally': not is_gdrive_url(resolved_path),
            **status_result,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _lookup_gdrive_view_copy_status(db_type, book_id):
    """book_id의 현재 뷰-복사 상태를 조회해 status/prefetch 응답 공통 딕셔너리로 만든다.
    도서 자체를 찾지 못하면 None, 찾았지만 gdrive 책이 아니면 status='not_applicable'."""
    from repositories.book_repository import BookRepository
    from repositories.gdrive_book_copy_repository import GdriveBookCopyRepository
    from utils.drive_helper import is_gdrive_url

    row = BookRepository.get_book_file_path_with_permission(db_type, book_id, '', [])
    if not row:
        return None

    if not is_gdrive_url(row['file_path']):
        return {'status': 'not_applicable'}

    copy_row = GdriveBookCopyRepository.get_by_book_id(db_type, book_id)
    if not copy_row:
        return {'status': 'not_copied'}

    return {
        'status': copy_row['status'],
        'local_path': copy_row.get('local_path'),
        'error_message': copy_row.get('error_message'),
        'updated_at': str(copy_row.get('updated_at')) if copy_row.get('updated_at') else None,
    }
