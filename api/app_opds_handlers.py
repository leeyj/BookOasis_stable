# -*- coding: utf-8 -*-
"""Shared handlers used by api/app_opds.py routes."""

from flask import Response, jsonify, request

from api.opds_common.xml import build_external_request_url, get_external_base_url

from services.book_detail_service import BookDetailService
from services.book_info_service import BookInfoService
from services.category_service import CategoryService
from services.opds_service import (
    EMPTY_SERIES_TOKEN,
    get_book_entries,
    get_library_list,
    get_recently_added_entries,
    get_recently_read_entries,
    get_series_entries,
    search_books_entries,
)
from services.series_service import SeriesService


class AppOpdsHandlers:
    def __init__(
        self,
        *,
        check_auth_cached,
        get_current_user,
        unauthorized,
        get_cached_response,
        set_cached_response,
        opds_xml,
        atom_response,
        parse_paging_args,
        get_page_params,
        filter_supported_series,
        filter_supported_books,
        enrich_books,
    ):
        self._check_auth_cached = check_auth_cached
        self._get_current_user = get_current_user
        self._unauthorized = unauthorized
        self._get_cached_response = get_cached_response
        self._set_cached_response = set_cached_response
        self._opds_xml = opds_xml
        self._atom_response = atom_response
        self._parse_paging_args = parse_paging_args
        self._get_page_params = get_page_params
        self._filter_supported_series = filter_supported_series
        self._filter_supported_books = filter_supported_books
        self._enrich_books = enrich_books

    def handle_root_feed(self, is_adult: bool):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()

        db_type = 'adult' if is_adult else 'general'
        cache_key = f"app_opds_root:{db_type}"

        cached_xml = self._get_cached_response(cache_key)
        if cached_xml is not None:
            return self._atom_response(cached_xml)

        libs = get_library_list(db_type)
        urn_prefix = 'urn:app:adult' if is_adult else 'urn:app'
        entries = [
            {
                'id': f"{urn_prefix}:library:{lib['id']}",
                'title': lib['name'],
                'type': 'navigation',
                'href': f"/app-opds/adult/library/{lib['id']}" if is_adult else f"/app-opds/library/{lib['id']}",
            }
            for lib in libs
        ]
        if is_adult:
            entries.extend([
                {'id': 'urn:app:adult:recently-added', 'title': '신규 추가', 'type': 'navigation', 'href': '/app-opds/adult/recently-added'},
                {'id': 'urn:app:adult:recently-read', 'title': '최근 읽은 도서', 'type': 'navigation', 'href': '/app-opds/adult/recently-read'},
            ])
            title = 'BookOasis App Adult OPDS Catalog'
        else:
            entries.extend([
                {'id': 'urn:app:recently-added', 'title': '신규 추가', 'type': 'navigation', 'href': '/app-opds/recently-added'},
                {'id': 'urn:app:recently-read', 'title': '최근 읽은 도서', 'type': 'navigation', 'href': '/app-opds/recently-read'},
            ])
            title = 'BookOasis App OPDS Catalog'

        xml = self._opds_xml(db_type, title, entries, is_adult=is_adult)
        self._set_cached_response(cache_key, xml)
        return self._atom_response(xml)

    def handle_media_api_compat(self, is_adult: bool):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()

        db_type = request.args.get('type', 'adult' if is_adult else 'general')
        if (not is_adult) and db_type == 'adult' and not self._check_auth_cached(is_adult=True):
            return self._unauthorized()

        library_id = request.args.get('library_id', 'all')
        search_query = request.args.get('search', '').strip()
        sort = request.args.get('sort', 'asc').strip().lower()

        try:
            if request.path.endswith('/all-list'):
                series_list = SeriesService.get_all_books_list(db_type, library_id)
                series_list = self._filter_supported_series(db_type, series_list)
                return jsonify({'success': True, 'series': series_list})

            page, limit = self._parse_paging_args(default_limit=30)
            series_list = SeriesService.get_books_list(db_type, library_id, page, limit, search_query, sort)
            series_list = self._filter_supported_series(db_type, series_list)
            has_more = len(series_list) > limit
            if has_more:
                series_list = series_list[:limit]
            return jsonify({'success': True, 'series': series_list, 'has_more': has_more})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    def handle_media_libraries_compat(self, is_adult: bool):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()

        db_type = request.args.get('type', 'adult' if is_adult else 'general')
        if (not is_adult) and db_type == 'adult' and not self._check_auth_cached(is_adult=True):
            return self._unauthorized()

        try:
            libraries = CategoryService.get_libraries(db_type, user_id=None, role='admin')
            return jsonify({'success': True, 'libraries': libraries})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    def handle_media_detail_compat(self, is_adult: bool):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()

        db_type = request.args.get('type', 'adult' if is_adult else 'general')
        if (not is_adult) and db_type == 'adult' and not self._check_auth_cached(is_adult=True):
            return self._unauthorized()

        series_name = request.args.get('series', '')
        library_id = request.args.get('library_id', 'all')

        try:
            meta, books_list = BookDetailService.get_media_detail(
                db_type,
                series_name,
                library_id,
                user_id=1,
                restrict_same_directory=False,
            )
            books_list = self._filter_supported_books(books_list)
            books_list = self._enrich_books(books_list, db_type, is_adult_prefix=is_adult)
            return jsonify({'success': True, 'meta': meta, 'books': books_list})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    def handle_book_info_compat(self, is_adult: bool, book_id: int):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()

        db_type = request.args.get('type', 'adult' if is_adult else 'general')
        if (not is_adult) and db_type == 'adult' and not self._check_auth_cached(is_adult=True):
            return self._unauthorized()

        try:
            info = BookInfoService.get_viewer_info(db_type, book_id)
            if info is None:
                return jsonify({'success': False, 'error': 'Book not found'}), 404
            return jsonify({'success': True, 'total_pages': info.get('total_pages', 0), 'cover_image': info.get('cover_image')})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    def handle_login_compat(self, is_adult: bool):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()
        return jsonify({'success': True})

    def handle_library_feed(self, is_adult: bool, lib_id: int):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()

        db_type = 'adult' if is_adult else 'general'
        cache_key = f"app_opds_library:{db_type}:{lib_id}"
        cached_xml = self._get_cached_response(cache_key)
        if cached_xml is not None:
            return self._atom_response(cached_xml)

        if is_adult:
            entries = get_series_entries('adult', lib_id, '/app-opds/adult/series', 'app:adult')
            xml = self._opds_xml('adult', 'Adult Library Series', entries, is_adult=True)
        else:
            entries = get_series_entries('general', lib_id, '/app-opds/series', 'app:general')
            xml = self._opds_xml('general', 'Library Series', entries)

        self._set_cached_response(cache_key, xml)
        return self._atom_response(xml)

    def handle_series_feed(self, is_adult: bool, lib_id: int, series_name: str):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()

        db_type = 'adult' if is_adult else 'general'
        page, page_size, offset = self._get_page_params()
        cache_key = f"app_opds_series:{db_type}:{lib_id}:{series_name}:{page}:{page_size}"
        cached_xml = self._get_cached_response(cache_key)
        if cached_xml is not None:
            return self._atom_response(cached_xml)

        resolved_series_name = '' if series_name == EMPTY_SERIES_TOKEN else series_name
        if is_adult:
            entries, total = get_book_entries('adult', lib_id, resolved_series_name, '/app-opds/download/adult', 'app:adult', limit=page_size, offset=offset)
        else:
            entries, total = get_book_entries('general', lib_id, resolved_series_name, '/app-opds/download/general', 'app:general', limit=page_size, offset=offset)

        next_link = None
        if offset + page_size < total:
            next_link = build_external_request_url(request, {'page': page + 1, 'page_size': page_size})

        if is_adult:
            xml = self._opds_xml('adult', f'Adult Series: {resolved_series_name}', entries, is_adult=True, next_link=next_link)
        else:
            xml = self._opds_xml('general', f'Series: {resolved_series_name}', entries, next_link=next_link)

        self._set_cached_response(cache_key, xml)
        return self._atom_response(xml)

    def handle_recently_feed(self, is_adult: bool, kind: str):
        user = self._get_current_user(is_adult=is_adult)
        if not user:
            return self._unauthorized()

        db_type = 'adult' if is_adult else 'general'
        cache_key = f"app_opds_recently_{kind}:{db_type}"
        if kind == 'read':
            cache_key = f"{cache_key}:{user['id']}"
        cached_xml = self._get_cached_response(cache_key)
        if cached_xml is not None:
            return self._atom_response(cached_xml)

        if kind == 'added':
            entries = get_recently_added_entries(db_type, f'/app-opds/download/{db_type}', f'app:{db_type}')
            title = '신규 추가'
        else:
            entries = get_recently_read_entries(db_type, f'/app-opds/download/{db_type}', f'app:{db_type}', user_id=user['id'])
            title = '최근 읽은 도서'

        xml = self._opds_xml(db_type, title, entries, is_adult=is_adult)
        self._set_cached_response(cache_key, xml)
        return self._atom_response(xml)

    def _build_opensearch_description(self, short_name: str, description: str, template_url: str):
        xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<OpenSearchDescription xmlns=\"http://a9.com/-/spec/opensearch/1.1/\">
  <ShortName>{short_name}</ShortName>
  <Description>{description}</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
  <Url type=\"application/atom+xml\" template=\"{template_url}\"/>
</OpenSearchDescription>"""
        return Response(xml, mimetype='application/opensearchdescription+xml; charset=utf-8')

    def handle_search_feed(self, is_adult: bool):
        if not self._check_auth_cached(is_adult=is_adult):
            return self._unauthorized()

        query = request.args.get('q') or request.args.get('query') or ''
        base_url = get_external_base_url(request)
        if not query:
            if is_adult:
                return self._build_opensearch_description('BookOasis App Adult', 'Search BookOasis App Adult Catalog', f'{base_url}/app-opds-adult/search?q={{searchTerms}}')
            return self._build_opensearch_description('BookOasis App', 'Search BookOasis App Catalog', f'{base_url}/app-opds/search?q={{searchTerms}}')

        page, page_size, offset = self._get_page_params()
        if is_adult:
            entries, total = search_books_entries('adult', query, '/app-opds/download/adult', 'app:adult', limit=page_size, offset=offset)
        else:
            entries, total = search_books_entries('general', query, '/app-opds/download/general', 'app:general', limit=page_size, offset=offset)

        next_link = None
        if offset + page_size < total:
            next_link = build_external_request_url(request, {'q': query, 'page': page + 1, 'page_size': page_size})

        if is_adult:
            xml = self._opds_xml('adult', f'성인 검색 결과: {query}', entries, is_adult=True, next_link=next_link)
        else:
            xml = self._opds_xml('general', f'검색 결과: {query}', entries, next_link=next_link)
        return self._atom_response(xml)
