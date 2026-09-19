# -*- coding: utf-8 -*-
"""
scan_routes.py – 스캔 관리 라우터 (도서 스캔, 표지 스캔 등)
"""
import os
from flask import Blueprint, request, jsonify
from services.book_scan_service import BookScanService
from api.auth import admin_required
from utils.i18n import _t
import database
from services.batch_book_scan_targets import resolve_batch_book_scan_targets

scan_bp = Blueprint('scan', __name__)
LAZY_SCAN_DB_TYPES = {'general', 'adult', 'audiobook'}

def get_db_path_for_scan(db_type):
    """db_type에 대응하는 스캔 대상 데이터베이스 경로/식별자 반환 (MariaDB 모드 대응)"""
    return database.get_db_path(db_type)


def _enqueue_targeted_lazy_scan(db_type, **target):
    from services.scanner_queue import scanner_queue
    return scanner_queue.enqueue('lazy_scan', db_type=db_type, **target)


@scan_bp.route('/api/media/books/lazy-scan', methods=['POST'])
@admin_required
def trigger_books_lazy_scan():
    """선택 도서 또는 특정 라이브러리의 전체 시리즈를 Lazy-Scanner로 보완한다."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    db_type = str(payload.get('type') or request.form.get('type') or 'general').strip().lower()
    if db_type not in LAZY_SCAN_DB_TYPES:
        return jsonify({'success': False, 'error': '지원하지 않는 도서 데이터베이스입니다.'}), 400

    raw_book_ids = payload.get('book_ids')
    if raw_book_ids is None:
        raw_book_ids = request.form.getlist('book_ids')

    raw_series_name = payload.get('series_name')
    raw_library_id = payload.get('library_id')
    if raw_series_name is not None or raw_library_id is not None:
        if raw_book_ids:
            return jsonify({'success': False, 'error': '도서 ID와 시리즈 대상은 함께 지정할 수 없습니다.'}), 400
        if not isinstance(raw_series_name, str) or not raw_series_name.strip():
            return jsonify({'success': False, 'error': '스캔할 시리즈명이 필요합니다.'}), 400
        if isinstance(raw_library_id, bool) or not str(raw_library_id).strip().isdecimal():
            return jsonify({'success': False, 'error': '시리즈 라이브러리 ID가 올바르지 않습니다.'}), 400
        library_id = int(raw_library_id)
        if library_id <= 0:
            return jsonify({'success': False, 'error': '시리즈 라이브러리 ID가 올바르지 않습니다.'}), 400
        series_name = raw_series_name.strip()
        if len(series_name) > 512:
            return jsonify({'success': False, 'error': '시리즈명이 너무 깁니다.'}), 400

        conn = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) AS book_count FROM books WHERE library_id = ? AND series_name = ?',
                (library_id, series_name),
            )
            row = cursor.fetchone()
            book_count = int(row['book_count'] or 0) if row else 0
            if book_count == 0:
                return jsonify({'success': False, 'error': '해당 라이브러리에서 시리즈 도서를 찾을 수 없습니다.'}), 404

            if not _enqueue_targeted_lazy_scan(
                db_type,
                library_id=library_id,
                series_name=series_name,
            ):
                return jsonify({
                    'success': False,
                    'error': 'Lazy-Scanner 작업이 이미 실행 중이거나 대기 중입니다. 현재 작업이 끝난 뒤 다시 요청해 주세요.'
                }), 409
            return jsonify({
                'success': True,
                'message': f"'{series_name}' 시리즈 {book_count}권의 Lazy-Scanner 작업을 대기열에 추가했습니다."
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()

    if not isinstance(raw_book_ids, list) or not raw_book_ids:
        return jsonify({'success': False, 'error': '스캔할 도서 ID가 필요합니다.'}), 400
    if len(raw_book_ids) > 500:
        return jsonify({'success': False, 'error': '한 번에 최대 500개 도서까지 요청할 수 있습니다.'}), 400

    try:
        book_ids = []
        for raw_id in raw_book_ids:
            if isinstance(raw_id, bool) or not str(raw_id).strip().isdecimal():
                raise ValueError('도서 ID는 양의 정수여야 합니다.')
            book_id = int(raw_id)
            if book_id <= 0:
                raise ValueError('도서 ID는 양의 정수여야 합니다.')
            if book_id not in book_ids:
                book_ids.append(book_id)
    except (TypeError, ValueError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    conn = None
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        placeholders = ', '.join('?' for _ in book_ids)
        cursor.execute(f"SELECT id FROM books WHERE id IN ({placeholders})", tuple(book_ids))
        found_ids = {int(row['id']) for row in cursor.fetchall()}
        if found_ids != set(book_ids):
            return jsonify({'success': False, 'error': '요청한 도서 중 현재 라이브러리에서 찾을 수 없는 항목이 있습니다.'}), 404

        if not _enqueue_targeted_lazy_scan(db_type, book_ids=book_ids):
            return jsonify({
                'success': False,
                'error': 'Lazy-Scanner 작업이 이미 실행 중이거나 대기 중입니다. 현재 작업이 끝난 뒤 다시 요청해 주세요.'
            }), 409
        return jsonify({
            'success': True,
            'message': f'선택한 {len(book_ids)}개 작품의 Lazy-Scanner 작업을 대기열에 추가했습니다.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@scan_bp.route('/api/media/books/<int:book_id>/scan', methods=['POST'])
@admin_required
def scan_single_book_api(book_id):
    """특정 개별 도서 즉시 부분 재스캔 실행"""
    db_type = request.form.get('type', 'general')
    try:
        success, message, cover_image = BookScanService.scan_single_book(db_type, book_id)
        if success:
            return jsonify({'success': True, 'message': message, 'cover_image': cover_image})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scan_bp.route('/api/media/books/scan-batch', methods=['POST'])
@admin_required
def enqueue_batch_book_scan():
    """선택한 여러 도서의 부분 재스캔을 백그라운드 큐에 등록한다."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    db_type = str(payload.get('type') or 'general').strip().lower()
    if db_type not in ('general', 'adult'):
        return jsonify({'success': False, 'error': '일반/성인 도서만 다중 스캔할 수 있습니다.'}), 400
    # scope는 요청이 명시한다(기본 book) - 시리즈 카드는 대표 권 ID만 보내므로 서버가 같은 시리즈의
    # 모든 권으로 확장한다. ID 개수로 스코프를 추정하지 않는다(상세 화면의 단일 권과 구분이 안 됨).
    scan_scope = str(payload.get('scope') or 'book').strip().lower()
    if scan_scope not in ('book', 'series'):
        return jsonify({'success': False, 'error': '지원하지 않는 스캔 범위입니다.'}), 400

    raw_book_ids = payload.get('book_ids')
    if not isinstance(raw_book_ids, list) or not raw_book_ids:
        return jsonify({'success': False, 'error': '스캔할 도서 ID가 필요합니다.'}), 400
    if len(raw_book_ids) > 500:
        return jsonify({'success': False, 'error': '한 번에 최대 500개 도서까지 요청할 수 있습니다.'}), 400

    book_ids = []
    try:
        for raw_id in raw_book_ids:
            if isinstance(raw_id, bool) or not str(raw_id).strip().isdecimal():
                raise ValueError('도서 ID는 양의 정수여야 합니다.')
            book_id = int(raw_id)
            if book_id <= 0:
                raise ValueError('도서 ID는 양의 정수여야 합니다.')
            if book_id not in book_ids:
                book_ids.append(book_id)
    except (TypeError, ValueError) as error:
        return jsonify({'success': False, 'error': str(error)}), 400

    conn = None
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            rows = resolve_batch_book_scan_targets(cursor, book_ids, scope=scan_scope)
        except LookupError as error:
            return jsonify({'success': False, 'error': str(error)}), 404
        if len(rows) > 500:
            return jsonify({'success': False, 'error': '시리즈 스캔은 한 번에 최대 500권까지 가능합니다.'}), 400
        book_ids = [int(row['id']) for row in rows]

        library_ids = {row['library_id'] for row in rows if row['library_id'] is not None}
        task_kwargs = {'db_type': db_type, 'book_ids': book_ids, 'scope': scan_scope}
        if len(rows) == len(book_ids) and len(library_ids) == 1:
            task_kwargs['library_id'] = next(iter(library_ids))
        if len(book_ids) == 1:
            task_kwargs['book_title'] = str(rows[0]['title'] or '').strip()

        from services.scanner_queue import scanner_queue
        if not scanner_queue.enqueue('batch_book_scan', **task_kwargs):
            return jsonify({
                'success': False,
                'error': '같은 다중 도서 스캔 작업이 이미 실행 중이거나 대기 중입니다.',
            }), 409

        if scan_scope == 'series':
            message = f'시리즈 전체 {len(book_ids)}권의 스캔을 대기열에 추가했습니다.'
        elif len(book_ids) == 1:
            message = '도서 스캔을 대기열에 추가했습니다.'
        else:
            message = f'선택한 {len(book_ids)}개 작품의 스캔을 대기열에 추가했습니다.'
        return jsonify({
            'success': True,
            'message': message + ' 스캔 활동에서 진행 상황을 확인할 수 있습니다.',
        }), 202
    except Exception as error:
        return jsonify({'success': False, 'error': str(error)}), 500
    finally:
        if conn:
            conn.close()

@scan_bp.route('/api/media/libraries/<int:library_id>/scan', methods=['POST'])
@admin_required
def trigger_library_scan(library_id):
    """지정된 라이브러리 카테고리 즉시 비동기 스캔 실행"""
    db_type = request.form.get('type', 'general')
    force_val = request.form.get('force', 'false').lower()
    force = force_val in ('true', '1')
    try:
        from repositories.category_repository import CategoryRepository
        lib_info = CategoryRepository.get_library_by_id(db_type, library_id)
        
        if not lib_info:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404
        
        physical_path = lib_info['physical_path']
        db_path = get_db_path_for_scan(db_type)
        
        print(
            f"[API-ScanTrigger] 🚀 User requested scan for library_id={library_id}, "
            f"db_type={db_type}, path='{physical_path}', force_raw='{force_val}', force={force}"
        )
        
        from services.scanner_queue import scanner_queue
        enqueued = scanner_queue.enqueue('library_scan', db_type=db_type, db_path=db_path, 
                             library_id=library_id, physical_path=physical_path, force=force, force_requeue=True, trigger_type='manual', is_cron=False)
        if not enqueued:
            print(f"[API-ScanTrigger WARNING] ❌ Enqueue rejected for library_id={library_id}")
            return jsonify({
                'success': False,
                'error': '동일 라이브러리 스캔이 이미 실행 중이거나 대기 중입니다.'
            }), 409
        
        print(f"[API-ScanTrigger SUCCESS] ✅ Library_id={library_id} scan task enqueued successfully.")
        return jsonify({'success': True, 'message': _t('api.msg_scan_started')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _resolve_library_scoped_path(physical_path, rel_path):
    """라이브러리 physical_path(복수 루트 가능) 기준 상대경로를 절대경로로 해석하고,
    경로 탈출(디렉터리 트래버설) 여부를 검증해서 반환한다. 유효하지 않으면 None."""
    from utils.drive_helper import is_gdrive_url

    roots = [p.strip() for p in str(physical_path or '').replace('\r', '').split('\n') if p.strip()]
    roots = [r for r in roots if not is_gdrive_url(r)]

    for root in roots:
        root_norm = os.path.normpath(root)
        candidate = os.path.normpath(os.path.join(root_norm, rel_path))
        root_cmp = os.path.normcase(root_norm)
        cand_cmp = os.path.normcase(candidate)
        if cand_cmp != root_cmp and not cand_cmp.startswith(root_cmp + os.sep):
            continue
        if os.path.exists(candidate):
            return candidate
    return None


@scan_bp.route('/api/media/libraries/<int:library_id>/scan-path', methods=['POST'])
@admin_required
def trigger_library_path_scan(library_id):
    """새로 추가한 특정 도서/시리즈 폴더 하나만 즉시 동기 스캔하여 등록 (주기 전체 스캔과 별개)"""
    db_type = request.form.get('type', 'general')
    rel_path = (request.form.get('path') or '').strip()
    force_val = request.form.get('force', 'false').lower()
    force = force_val in ('true', '1')

    if not rel_path:
        return jsonify({'success': False, 'error': '스캔할 경로(path)가 필요합니다.'}), 400

    try:
        from repositories.category_repository import CategoryRepository
        lib_info = CategoryRepository.get_library_by_id(db_type, library_id)
        if not lib_info:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404

        target_path = _resolve_library_scoped_path(lib_info['physical_path'], rel_path)
        if not target_path:
            return jsonify({'success': False, 'error': '해당 경로를 라이브러리 내에서 찾을 수 없습니다.'}), 404

        db_path = get_db_path_for_scan(db_type)

        print(
            f"[API-ScanPath] 🎯 User requested single-path scan for library_id={library_id}, "
            f"db_type={db_type}, path='{target_path}', force={force}"
        )

        from tools.scanner.core import scan_library_path
        scan_library_path(db_path, library_id, target_path, force=force)

        # 이 경로는 scanner_queue를 거치지 않는 동기 단건 스캔이라 큐 완료 시 캐시 소거가
        # 실행되지 않으므로, 신규 등록 도서가 반영되지 않은 대시보드 캐시가 남지 않도록 직접 소거한다.
        try:
            from utils.redis_helper import redis_delete_pattern
            redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
            redis_delete_pattern(f"cache:history*:{db_type}:*")
        except Exception as cache_err:
            print(f"[API-ScanPath WARNING] 레디스 캐시 소거 실패: {cache_err}")

        return jsonify({'success': True, 'message': '지정한 경로의 스캔 및 등록이 완료되었습니다.'})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scan_bp.route('/api/media/libraries/<int:library_id>/cancel-scan', methods=['POST'])
@admin_required
def cancel_library_scan(library_id):
    """지정된 라이브러리 카테고리의 진행 중인 스캔을 중단하도록 플래그 갱신"""
    db_type = request.form.get('type', 'general')
    try:
        from repositories.category_repository import CategoryRepository
        CategoryRepository.update_library_scan_status(db_type, library_id, 'cancelling')
        return jsonify({'success': True, 'message': _t('api.msg_scan_cancelling')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scan_bp.route('/api/media/libraries/<int:library_id>/scan-covers', methods=['POST'])
@admin_required
def trigger_library_cover_scan(library_id):
    """지정된 라이브러리 카테고리 표지 전용 즉시 비동기 스캔 실행"""
    db_type = request.form.get('type', 'general')
    try:
        from repositories.category_repository import CategoryRepository
        lib_info = CategoryRepository.get_library_by_id(db_type, library_id)
        
        if not lib_info:
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404
        
        physical_path = lib_info['physical_path']
        db_path = get_db_path_for_scan(db_type)
        
        from services.scanner_queue import scanner_queue
        enqueued = scanner_queue.enqueue('cover_scan', db_type=db_type, db_path=db_path, 
                             library_id=library_id, physical_path=physical_path, force_requeue=True)
        if not enqueued:
            return jsonify({
                'success': False,
                'error': '동일 라이브러리 표지 스캔이 이미 실행 중이거나 대기 중입니다.'
            }), 409
        
        return jsonify({'success': True, 'message': _t('api.msg_cover_scan_started')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scan_bp.route('/api/media/libraries/<int:library_id>/lazy-scan', methods=['POST'])
@admin_required
def trigger_library_lazy_scan(library_id):
    """지정 라이브러리 안의 Lazy-Scanner 후보만 보완 작업 큐에 추가한다."""
    db_type = str(request.form.get('type', 'general')).strip().lower()
    if db_type not in LAZY_SCAN_DB_TYPES:
        return jsonify({'success': False, 'error': '지원하지 않는 도서 데이터베이스입니다.'}), 400
    try:
        from repositories.category_repository import CategoryRepository
        if not CategoryRepository.get_library_by_id(db_type, library_id):
            return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 404

        if not _enqueue_targeted_lazy_scan(db_type, library_id=library_id):
            return jsonify({
                'success': False,
                'error': 'Lazy-Scanner 작업이 이미 실행 중이거나 대기 중입니다. 현재 작업이 끝난 뒤 다시 요청해 주세요.'
            }), 409
        return jsonify({
            'success': True,
            'message': f'라이브러리 ID {library_id}의 Lazy-Scanner 작업을 대기열에 추가했습니다.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scan_bp.route('/api/media/libraries/scan-all', methods=['POST'])
@admin_required
def trigger_all_libraries_scan():
    """모든 라이브러리 카테고리를 순차적으로 대기열(큐)에 적재하여 전체 스캔 실행
    (group_id가 주어지면 해당 가상 그룹에 속한 카테고리만 대상으로 좁힌다 - 사이드바
    그룹 컨텍스트 메뉴의 "하위 카테고리 일괄 스캔")"""
    db_type = request.form.get('type', 'general')
    force_val = request.form.get('force', 'false').lower()
    force = force_val in ('true', '1')
    group_id_raw = request.form.get('group_id', '').strip()
    try:
        from repositories.category_repository import CategoryRepository
        rows = CategoryRepository.get_all_libraries(db_type)

        if group_id_raw:
            try:
                group_id = int(group_id_raw)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': _t('api.err_library_not_found')}), 400
            rows = [r for r in rows if r.get('group_id') == group_id]

        if not rows:
            return jsonify({'success': False, 'error': _t('api.err_no_libraries')}), 404

        db_path = get_db_path_for_scan(db_type)
        from services.scanner_queue import scanner_queue

        enqueued_count = 0
        skipped_count = 0
        for r in rows:
            res = scanner_queue.enqueue('library_scan', db_type=db_type, db_path=db_path, 
                                        library_id=r['id'], physical_path=r['physical_path'], force=force, force_requeue=True, trigger_type='manual', is_cron=False)
            if res:
                enqueued_count += 1
            else:
                skipped_count += 1
            
        return jsonify({'success': True, 'message': f'{enqueued_count}개의 카테고리가 순차 스캔 대기열에 추가되었습니다. (중복 제외: {skipped_count})'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scan_bp.route('/api/media/scan-history', methods=['GET'])
@admin_required
def get_scan_history_api():
    """최근 스캔 이력 목록 (최대 20건, 레이지스캔 제외) 조회. 상대시간("N분 전")은 프론트엔드에서
    static/js/utils/time.js의 formatRelativeTime()으로 계산한다 (응답 캐시 시 서버 렌더값이 stale해지는 것을 피함)."""
    try:
        from repositories.scanner_queue_repository import ScannerQueueRepository
        history = ScannerQueueRepository.get_scan_history(limit=20)

        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
