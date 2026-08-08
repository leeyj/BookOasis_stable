from unittest.mock import patch

from flask import Flask

from api.routes.library_routes import library_bp
from api.routes.media_library_routes import media_library_routes_bp
from services.category_service import CategoryService
from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA


def _create_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-library-groups')
    app.register_blueprint(library_bp)
    app.register_blueprint(media_library_routes_bp)
    return app


def _login(client, role='user'):
    with client.session_transaction() as session:
        session['user_id'] = 7
        session['role'] = role
        session['is_default_password'] = 0


def test_non_admin_only_receives_groups_with_visible_libraries():
    client = _create_app().test_client()
    _login(client)
    libraries = [{'id': 10, 'name': 'Visible library', 'group_id': 1}]
    groups = [{'id': 1, 'name': 'Visible'}, {'id': 2, 'name': 'Hidden'}]

    with patch(
        'api.routes.media_library_routes.CategoryService.get_libraries',
        return_value=libraries,
    ), patch(
        'api.routes.media_library_routes.CategoryService.get_library_groups',
        return_value=groups,
    ):
        response = client.get('/api/media/libraries?type=general')

    assert response.status_code == 200
    assert response.get_json()['groups'] == [groups[0]]


def test_group_crud_requires_admin():
    client = _create_app().test_client()
    _login(client)

    response = client.post(
        '/api/media/library-groups/add',
        data={'type': 'general', 'name': 'Denied'},
    )

    assert response.status_code == 403


def test_admin_can_create_group():
    client = _create_app().test_client()
    _login(client, role='admin')

    with patch(
        'api.routes.library_routes.CategoryService.add_library_group',
        return_value=3,
    ):
        response = client.post(
            '/api/media/library-groups/add',
            data={'type': 'general', 'name': 'Allowed'},
        )

    assert response.status_code == 200
    assert response.get_json()['group_id'] == 3


def test_mariadb_schema_contains_library_group_storage():
    assert 'CREATE TABLE IF NOT EXISTS library_groups' in MARIADB_CENTRAL_SCHEMA
    assert 'group_id BIGINT DEFAULT NULL' in MARIADB_CENTRAL_SCHEMA
    assert 'sort_order INT DEFAULT 0' in MARIADB_CENTRAL_SCHEMA
    assert 'idx_libraries_group_id' in MARIADB_CENTRAL_SCHEMA
    assert 'idx_libraries_group_order' in MARIADB_CENTRAL_SCHEMA


def test_move_libraries_requires_admin():
    client = _create_app().test_client()
    _login(client)

    response = client.post('/api/media/libraries/move', json={
        'type': 'general',
        'items': [{'id': 1, 'group_id': None}],
    })

    assert response.status_code == 403


def test_admin_can_move_libraries():
    client = _create_app().test_client()
    _login(client, role='admin')
    items = [{'id': 2, 'group_id': 3}, {'id': 1, 'group_id': None}]

    with patch('api.routes.library_routes.CategoryService.move_libraries') as move_libraries:
        response = client.post('/api/media/libraries/move', json={
            'type': 'general',
            'items': items,
        })

    assert response.status_code == 200
    move_libraries.assert_called_once_with('general', items)


def test_move_libraries_normalizes_order_per_group():
    items = [
        {'id': 2, 'group_id': 7},
        {'id': 3, 'group_id': None},
        {'id': 1, 'group_id': 7},
    ]
    libraries = [{'id': 1}, {'id': 2}, {'id': 3}]

    with patch('services.category_service.CategoryRepository.get_all_libraries', return_value=libraries), patch(
        'services.category_service.CategoryRepository.get_library_groups',
        return_value=[{'id': 7}],
    ), patch('services.category_service.CategoryRepository.move_libraries') as move_libraries:
        CategoryService.move_libraries('general', items)

    move_libraries.assert_called_once_with('general', [
        {'id': 2, 'group_id': 7, 'sort_order': 1},
        {'id': 3, 'group_id': None, 'sort_order': 1},
        {'id': 1, 'group_id': 7, 'sort_order': 2},
    ])
