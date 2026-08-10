from unittest.mock import patch

from flask import Flask

from api.routes.permission_routes import permission_bp


def _create_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-plugin-permissions')
    app.register_blueprint(permission_bp)
    return app


def _login_admin(client):
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['role'] = 'admin'
        session['is_default_password'] = 0


def test_plugin_permission_accepts_string_library_id():
    client = _create_app().test_client()
    _login_admin(client)

    with patch(
        'api.routes.permission_routes.SettingsRepository.set_value'
    ) as set_value, patch(
        'api.routes.permission_routes.UserRepository.update_category_permission'
    ) as update_category_permission:
        response = client.post(
            '/api/admin/permissions/update',
            json={
                'user_id': 7,
                'library_id': 'plugin_stats_dashboard',
                'has_access': False,
                'target_db': 'plugin',
            },
        )

    assert response.status_code == 200
    assert response.get_json()['success'] is True
    set_value.assert_called_once_with(
        'general', 'PERM_CATEGORY_7_plugin_stats_dashboard', '0'
    )
    update_category_permission.assert_not_called()