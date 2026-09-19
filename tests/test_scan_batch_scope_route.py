import sqlite3
from unittest.mock import patch

from flask import Flask

from api.routes.scan_routes import scan_bp


def _create_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-scan-batch-scope')
    app.register_blueprint(scan_bp)
    return app


def _admin_client():
    client = _create_app().test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['role'] = 'admin'
        session['is_default_password'] = 0
    return client


def _books_connection():
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute(
        'CREATE TABLE books (id INTEGER PRIMARY KEY, library_id INTEGER, title TEXT, '
        'series_name TEXT, is_deleted INTEGER DEFAULT 0)'
    )
    connection.executemany(
        'INSERT INTO books (id, library_id, title, series_name) VALUES (?, ?, ?, ?)',
        [(1, 2, 'S 01', 'S'), (2, 2, 'S 02', 'S'), (3, 2, 'S 03', 'S'), (4, 2, 'Other', 'O')],
    )
    connection.commit()
    return connection


def _post(payload):
    client = _admin_client()
    connection = _books_connection()
    with patch('api.routes.scan_routes.database.get_connection', return_value=connection), \
            patch('services.scanner_queue.scanner_queue.enqueue', return_value=True) as enqueue:
        response = client.post('/api/media/books/scan-batch', json=payload)
    return response, enqueue


def test_missing_scope_keeps_existing_single_book_behavior():
    response, enqueue = _post({'type': 'general', 'book_ids': [1]})

    assert response.status_code == 202
    kwargs = enqueue.call_args.kwargs
    assert kwargs['book_ids'] == [1]
    assert kwargs['scope'] == 'book'


def test_series_scope_expands_anchor_to_every_volume():
    response, enqueue = _post({'type': 'general', 'book_ids': [1], 'scope': 'series'})

    assert response.status_code == 202
    assert enqueue.call_args.kwargs['book_ids'] == [1, 2, 3]
    assert '3권' in response.get_json()['message']


def test_invalid_scope_is_rejected_without_enqueue():
    response, enqueue = _post({'type': 'general', 'book_ids': [1], 'scope': 'everything'})

    assert response.status_code == 400
    enqueue.assert_not_called()


def test_unknown_book_id_returns_404_without_enqueue():
    response, enqueue = _post({'type': 'general', 'book_ids': [999], 'scope': 'series'})

    assert response.status_code == 404
    enqueue.assert_not_called()
