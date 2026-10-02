"""OPDS-PSE 페이지 스트리밍 (KOReader 등이 만화를 내려받지 않고 페이지 단위로 보기)."""
from unittest.mock import patch

from flask import Flask

from api import opds as opds_api
from api.opds_common.xml_opds import build_opds_standard_xml
from services import opds_service


def _entry(book_id, path):
    return {'id': f'urn:general:book:{book_id}', 'title': f'B{book_id}', 'type': 'acquisition',
            'href': f'/opds/download/general/{book_id}', 'mime': 'application/vnd.comicbook+zip',
            'book_id': book_id, 'file_path': path}


def test_pse_links_go_on_archives_with_a_known_page_count_only():
    entries = [_entry(1, '/b/One 01.cbz'), _entry(2, '/b/Two.zip'), _entry(3, '/b/Novel.epub'), _entry(4, '/b/Unscanned.zip')]
    with patch.object(opds_service.OpdsRepository, 'get_total_pages', return_value={1: 180, 2: 24, 4: 0}) as lookup:
        opds_service._attach_pse_links('general', entries, is_app_opds=False)

    lookup.assert_called_once_with('general', [1, 2, 4])          # EPUB은 묻지도 않는다
    assert [(e.get('pse_href'), e.get('pse_count')) for e in entries] == [
        ('/opds/pse/general/1/{pageNumber}', 180), ('/opds/pse/general/2/{pageNumber}', 24), (None, None), (None, None)]


def test_app_opds_feeds_do_not_get_pse_links():
    entries = [_entry(1, '/b/One.cbz')]
    with patch.object(opds_service.OpdsRepository, 'get_total_pages') as lookup:
        opds_service._attach_pse_links('general', entries, is_app_opds=True)
    lookup.assert_not_called()
    assert 'pse_href' not in entries[0]


def test_feed_xml_declares_the_pse_namespace_and_stream_link():
    app = Flask(__name__)
    entry = {**_entry(1, '/b/One.cbz'), 'pse_href': '/opds/pse/general/1/{pageNumber}', 'pse_count': 180}
    with app.test_request_context('/opds/series/2/One', base_url='http://server:5930'):
        from flask import request
        xml = build_opds_standard_xml(request, 'S', [entry], '/opds', '/opds/search')
    assert 'xmlns:pse="http://vaemendis.net/opds-pse/ns"' in xml
    assert ('<link rel="http://vaemendis.net/opds-pse/stream" type="image/jpeg" '
            'href="http://server:5930/opds/pse/general/1/{pageNumber}" pse:count="180"/>') in xml


def _client():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='t')
    app.register_blueprint(opds_api.opds_bp)
    return app.test_client()


def test_page_route_serves_the_page_for_basic_auth_users():
    with patch.object(opds_api, '_get_authenticated_user', return_value={'id': 7, 'role': 'user'}), \
            patch('services.app_opds_viewer_service.get_stream_page',
                  return_value={'status': 'ok', 'img_data': b'jpeg', 'mime_type': 'image/jpeg'}) as page:
        response = _client().get('/opds/pse/general/42/3')
    assert response.status_code == 200 and response.data == b'jpeg' and response.mimetype == 'image/jpeg'
    page.assert_called_once_with('general', 42, 3, user_id=7, role='user')


def test_page_route_accepts_the_signed_token_and_records_progress_for_its_user():
    token = opds_api._make_download_token('general', 42, 9)
    with patch.object(opds_api, '_get_authenticated_user', return_value=None), \
            patch('services.app_opds_viewer_service.get_stream_page',
                  return_value={'status': 'ok', 'img_data': b'jpeg', 'mime_type': 'image/jpeg'}) as page:
        ok = _client().get(f'/opds/pse/general/42/0?token={token}')
        other_book = _client().get(f'/opds/pse/general/43/0?token={token}')   # 다른 책 토큰은 안 됨
        no_token = _client().get('/opds/pse/general/42/0')
    assert ok.status_code == 200
    page.assert_called_once_with('general', 42, 0, user_id=9, role='admin')
    assert other_book.status_code == 401 and no_token.status_code == 401


def test_sign_secret_is_no_longer_the_public_default():
    assert opds_api._SIGN_SECRET != 'bookoasis-opds-sign-2026'
