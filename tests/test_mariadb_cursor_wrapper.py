from database import DictRow, MariadbCursorWrapper


class _RawCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


def test_fetchone_dict_row_supports_key_and_index_access():
    cursor = MariadbCursorWrapper(_RawCursor([{'value': 'legacy'}]))

    row = cursor.fetchone()

    assert isinstance(row, DictRow)
    assert row['value'] == 'legacy'
    assert row[0] == 'legacy'


def test_fetchall_dict_rows_support_key_and_index_access():
    cursor = MariadbCursorWrapper(_RawCursor([{'count': 0}, {'count': 2}]))

    rows = cursor.fetchall()

    assert [row['count'] for row in rows] == [0, 2]
    assert [row[0] for row in rows] == [0, 2]