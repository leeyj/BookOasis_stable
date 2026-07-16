from flask import Blueprint, request, jsonify, session
import sqlite3
from services.category_service import CategoryService
from services.book_service import BookService
from services.series_service import SeriesService
from services.book_detail_service import BookDetailService
from services.metadata_service import MetadataService
from services.reading_history_service import ReadingHistoryService
from services.library_service import LibraryService
from services.book_info_service import BookInfoService
from services.plugin_service import PluginService
from api.auth import login_required, check_adult_permission, admin_required
from utils.i18n import _t

library_bp = Blueprint('media_library', __name__)

@library_bp.route('/api/media/libraries', methods=['GET'])
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

@library_bp.route('/api/media/list', methods=['GET'])
@login_required
def get_media_list():
    """도서 보관함 시리즈 목록 조회 (무한 스크롤 페이지네이션 + 서버 검색)"""
    db_type    = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    library_id = request.args.get('library_id')
    search_query = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'asc').strip().lower()
    try:
        page  = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 30))
    except ValueError:
        page, limit = 1, 30

    try:
        series_list = SeriesService.get_books_list(db_type, library_id, page, limit, search_query, sort)
        has_more = len(series_list) > limit
        if has_more:
            series_list = series_list[:limit]
        return jsonify({'success': True, 'series': series_list, 'has_more': has_more})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/all-list', methods=['GET'])
@login_required
def get_media_all_list():
    """Kavita 방식의 선로드를 위해 특정 라이브러리의 전체 시리즈 목록을 페이징 없이 경량 조회"""
    db_type    = request.args.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    library_id = request.args.get('library_id')
    try:
        series_list = SeriesService.get_all_books_list(db_type, library_id)
        return jsonify({'success': True, 'series': series_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/detail', methods=['GET'])
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

    try:
        meta, books_list = BookDetailService.get_media_detail(
            db_type,
            series_name,
            library_id,
            user_id=user_id,
            representative_book_id=representative_book_id
        )
        return jsonify({'success': True, 'meta': meta, 'books': books_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/detail/edit', methods=['POST'])
@admin_required
def edit_media_detail():
    """시리즈 메타정보 수동 수정 및 표지 업로드"""
    db_type     = request.form.get('type', 'general')
    series_name = request.form.get('series', '').strip()
    author      = request.form.get('author', '').strip()
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
            publisher=publisher,
            summary=summary,
            link=link,
            genre=genre,
            tags=tags,
            cover_file=cover_file
        )
        return jsonify({'success': success, 'message': message if success else None, 'error': message if not success else None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/tags', methods=['GET'])
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

@library_bp.route('/api/media/genres', methods=['GET'])
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

@library_bp.route('/api/media/history', methods=['GET'])
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

@library_bp.route('/api/media/recently-added', methods=['GET'])
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



@library_bp.route('/api/media/meta/recommend', methods=['GET'])
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

@library_bp.route('/api/media/meta/copy', methods=['POST'])
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

@library_bp.route('/api/media/next-book', methods=['GET'])
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

@library_bp.route('/api/media/books/<int:book_id>/info', methods=['GET'])
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

@library_bp.route('/api/media/books/<int:book_id>/favorite', methods=['POST', 'PATCH'])
@login_required
def toggle_book_favorite(book_id):
    """특정 도서의 즐겨찾기 상태 변경"""
    db_type = request.form.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    try:
        is_favorite = int(request.form.get('is_favorite', 0))
    except ValueError:
        is_favorite = 0

    try:
        BookService.update_favorite(db_type, book_id, is_favorite)
        return jsonify({'success': True, 'message': _t('api.msg_favorite_updated')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@library_bp.route('/api/media/series/favorite', methods=['POST', 'PATCH'])
@login_required
def toggle_series_favorite_api():
    """특정 시리즈 전체의 즐겨찾기 상태 변경"""
    db_type = request.form.get('type', 'general')
    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403
    series_name = request.form.get('series_name', '').strip()
    try:
        is_favorite = int(request.form.get('is_favorite', 0))
    except ValueError:
        is_favorite = 0

    if not series_name:
        return jsonify({'success': False, 'error': 'series_name이 누락되었습니다.'}), 400

    try:
        BookService.update_series_favorite(db_type, series_name, is_favorite)
        return jsonify({'success': True, 'message': _t('api.msg_series_favorite_updated')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/metadata/plugins', methods=['GET'])
@admin_required
def get_metadata_plugins_api():
    """수동 검색 모달에 사용 가능한 메타데이터 플러그인 목록 조회"""
    try:
        plugins = MetadataService.get_searchable_plugins()
        return jsonify({'success': True, 'plugins': plugins})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@library_bp.route('/api/media/metadata/plugins/manage', methods=['GET'])
@admin_required
def get_metadata_plugins_manage_api():
    """환경설정 > 플러그인 관리에 표시할 전체 메타데이터 플러그인 목록 조회"""
    try:
        from services.metadata_factory import MetadataFactory

        plugins = MetadataFactory.get_available_providers()
        return jsonify({'success': True, 'plugins': plugins})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/books/search-metadata', methods=['GET'])
@admin_required
def search_book_metadata_api():
    """지정된 메타데이터 플러그인을 활용하여 도서 메타데이터 후보군 검색"""
    db_type = request.args.get('type', 'general')
    query = request.args.get('query', '').strip()
    source = request.args.get('source', '').strip() or None
    
    if not query:
        return jsonify({'success': False, 'error': _t('api.err_query_missing')}), 400
        
    try:
        results = MetadataService.search_metadata(db_type, query, source)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/books/<int:book_id>/apply-metadata', methods=['POST'])
@admin_required
def apply_book_metadata_api(book_id):
    """사용자가 선택한 메타데이터 정보를 도서 정보에 최종 반영"""
    db_type = request.json.get('type', 'general') if request.is_json else request.form.get('type', 'general')
    source = request.json.get('source') if request.is_json else request.form.get('source')
    source = source.strip() if source else None
    
    # 하위 호환 및 신규 규격 대응
    item_data = None
    if request.is_json:
        item_data = request.json.get('item_data') or request.json.get('aladin_item')
    else:
        # form 전송일 때
        item_data = request.form.to_dict()
        if 'type' in item_data:
            item_data.pop('type')
        if 'source' in item_data:
            item_data.pop('source')

    if not item_data:
        return jsonify({'success': False, 'error': _t('api.err_metadata_missing')}), 400
        
    try:
        success, message = MetadataService.apply_metadata(db_type, book_id, item_data, source)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/metadata/plugins/toggle', methods=['POST'])
@admin_required
def toggle_metadata_plugin_api():
    """특정 플러그인의 ON/OFF 활성화 상태를 업데이트합니다."""
    db_type = request.form.get('type', 'general')
    plugin_id = request.form.get('plugin_id', '').strip()
    enabled_val = request.form.get('enabled', '1').strip()
    
    if not plugin_id:
        return jsonify({'success': False, 'error': _t('api.err_plugin_id_missing')}), 400
        
    try:
        success, error = PluginService.toggle_plugin_enabled(db_type, plugin_id, enabled_val)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        status_txt = _t('api.status_enabled') if enabled_val == '1' else _t('api.status_disabled')
        return jsonify({'success': True, 'message': _t('api.msg_plugin_status_updated', plugin_id=plugin_id, status_txt=status_txt)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/metadata/plugins/save-config', methods=['POST'])
@admin_required
def save_metadata_plugin_config_api():
    """특정 플러그인의 JSON 설정 데이터를 DB에 저장합니다."""
    db_type = request.json.get('type', 'general') if request.is_json else request.form.get('type', 'general')
    plugin_id = request.json.get('plugin_id') if request.is_json else request.form.get('plugin_id')
    config_data = request.json.get('config') if request.is_json else request.form.get('config')
    
    if not plugin_id:
        return jsonify({'success': False, 'error': _t('api.err_plugin_id_missing')}), 400
        
    if config_data is None:
        return jsonify({'success': False, 'error': _t('api.err_config_data_missing')}), 400
        
    try:
        success, error = PluginService.save_plugin_config(db_type, plugin_id, config_data)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        return jsonify({'success': True, 'message': _t('api.msg_plugin_config_saved', plugin_id=plugin_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@library_bp.route('/api/media/dashboard/widgets', methods=['GET'])
def get_dashboard_widgets_api():
    """대시보드에 표시할 활성화된 위젯(플러그인) 목록을 반환합니다."""
    db_type = request.args.get('type', 'general').strip()
    try:
        from services.metadata_factory import MetadataFactory
        providers = MetadataFactory.get_available_providers()

        active_widgets = []
        for p in providers:
            if not p.get('enabled'):
                continue
            widget = p.get('dashboard_widget')
            if not isinstance(widget, dict):
                continue

            # 라이브러리 타입(general / adult) 노출 필터링 (생략 시 둘 다 노출)
            supported_types = widget.get('supported_types')
            if isinstance(supported_types, list) and db_type not in supported_types:
                continue

            active_widgets.append({
                'id': p.get('id'),
                'name': p.get('name'),
                'title': widget.get('title') or p.get('name'),
                'subtitle': widget.get('subtitle') or '',
                'provider': widget.get('provider') or p.get('name'),
                'icon': widget.get('icon') or 'fa-solid fa-puzzle-piece',
                'limit': int(widget.get('limit') or 10),
                'all_desk_tab': bool(widget.get('all_desk_tab') or False),
            })

        return jsonify({'success': True, 'widgets': active_widgets}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@library_bp.route('/api/media/dashboard/widgets/<plugin_id>/data', methods=['GET'])
def get_dashboard_widget_data_api(plugin_id):
    """대시보드 위젯 데이터 조회 (플러그인 동적 로딩)."""
    db_type = request.args.get('type', 'general')
    limit = int(request.args.get('limit', 10))

    try:
        from services.metadata_factory import MetadataFactory
        provider = MetadataFactory.get_provider_by_id(plugin_id)

        result = provider.get_dashboard_data(db_type, limit=limit)

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@library_bp.route('/api/media/context-menu/book/plugins', methods=['POST'])
@login_required
def get_book_context_menu_plugin_items_api():
    """활성화된 플러그인의 도서 컨텍스트 메뉴 항목을 동적으로 조회합니다."""
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('type', 'general')
    print(f"[ContextMenuAPI] items request db_type={db_type!r} payload={payload!r}")

    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    context = payload.get('context') or {}

    try:
        from services.metadata_factory import MetadataFactory

        providers = MetadataFactory.get_available_providers()
        print(f"[ContextMenuAPI] discovered providers={[p.get('id') for p in providers]!r}")
        merged_items = []

        for provider_meta in providers:
            if not provider_meta.get('enabled'):
                continue

            provider_id = provider_meta.get('id')
            if not provider_id:
                continue

            try:
                provider = MetadataFactory.get_provider_by_id(provider_id)
                print(f"[ContextMenuAPI] loading provider_id={provider_id!r} class={provider.__class__.__name__!r}")
                items = provider.get_context_menu_items(db_type, context) or []
                print(f"[ContextMenuAPI] provider_id={provider_id!r} returned items={items!r}")
            except Exception:
                import traceback
                print(f"[ContextMenuAPI] provider_id={provider_id!r} item load failed:\n{traceback.format_exc()}")
                items = []

            if not isinstance(items, list):
                continue

            for raw_item in items:
                if not isinstance(raw_item, dict):
                    continue

                action_id = str(raw_item.get('id') or '').strip()
                label = str(raw_item.get('label') or '').strip()
                if not action_id or not label:
                    continue

                merged_items.append({
                    'plugin_id': provider_id,
                    'plugin_name': provider_meta.get('name') or provider_id,
                    'id': action_id,
                    'label': label,
                    'icon': raw_item.get('icon') or 'fa-solid fa-puzzle-piece',
                })

        print(f"[ContextMenuAPI] merged items count={len(merged_items)}")
        return jsonify({'success': True, 'items': merged_items}), 200
    except Exception as e:
        import traceback
        print(f"[ContextMenuAPI] items fatal error:\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


@library_bp.route('/api/media/context-menu/book/plugins/action', methods=['POST'])
@login_required
def run_book_context_menu_plugin_action_api():
    """도서 컨텍스트 메뉴에서 선택된 플러그인 액션을 실행합니다."""
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('type', 'general')
    print(f"[ContextMenuAPI] action request db_type={db_type!r} payload={payload!r}")

    if not check_adult_permission(db_type):
        return jsonify({'success': False, 'error': _t('api.err_no_adult_access')}), 403

    plugin_id = (payload.get('plugin_id') or '').strip()
    action_id = (payload.get('action_id') or '').strip()
    context = payload.get('context') or {}

    if not plugin_id:
        return jsonify({'success': False, 'error': 'plugin_id가 누락되었습니다.'}), 400
    if not action_id:
        return jsonify({'success': False, 'error': 'action_id가 누락되었습니다.'}), 400

    try:
        from services.metadata_factory import MetadataFactory

        provider = MetadataFactory.get_provider_by_id(plugin_id)
        print(f"[ContextMenuAPI] action provider_id={plugin_id!r} class={provider.__class__.__name__!r} action_id={action_id!r}")
        result = provider.run_context_menu_action(db_type, action_id, context)
        print(f"[ContextMenuAPI] action result={result!r}")
        if not isinstance(result, dict):
            result = {'success': False, 'error': '플러그인 액션 반환값 형식이 올바르지 않습니다.'}

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except ValueError as ve:
        print(f"[ContextMenuAPI] value error: {ve}")
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        import traceback
        print(f"[ContextMenuAPI] action fatal error:\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500
