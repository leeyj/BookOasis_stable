from repositories.mariadb import reading_progress_repository as repository_module


class FakeCursor:
    def __init__(self, batches):
        self.batches = iter(batches)
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))

    def fetchall(self):
        return next(self.batches)


class FakeConnection:
    def __init__(self, batches):
        self.cursor_instance = FakeCursor(batches)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_mariadb_history_hides_completed_across_batches(monkeypatch):
    first_batch = [
        {'id': index, 'has_unfinished_siblings': 1 if index == 10 else 0}
        for index in range(50)
    ]
    second_batch = [{'id': 50, 'has_unfinished_siblings': 1}]
    connection = FakeConnection([first_batch, second_batch])
    monkeypatch.setattr(
        repository_module.database,
        'get_connection',
        lambda _db_type: connection,
    )

    rows = repository_module.ReadingProgressRepository.fetch_reading_history(
        'general', user_id=7, limit=2, hide_completed=True
    )

    assert [row['id'] for row in rows] == [10, 50]
    assert [call[1] for call in connection.cursor_instance.calls] == [
        (7, 50, 0),
        (7, 50, 50),
    ]
    assert connection.closed is True


def test_mariadb_history_without_filter_uses_single_limited_batch(monkeypatch):
    connection = FakeConnection([[
        {'id': 1, 'has_unfinished_siblings': 0},
        {'id': 2, 'has_unfinished_siblings': 1},
    ]])
    monkeypatch.setattr(
        repository_module.database,
        'get_connection',
        lambda _db_type: connection,
    )

    rows = repository_module.ReadingProgressRepository.fetch_reading_history(
        'general', user_id=3, limit=2, hide_completed=False
    )

    assert [row['id'] for row in rows] == [1, 2]
    assert connection.cursor_instance.calls[0][1] == (3, 2, 0)
    assert connection.closed is True