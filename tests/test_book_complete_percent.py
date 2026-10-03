"""도서 완독 기준(%) - 내 설정 BOOK_COMPLETE_PERCENT (기본 95, 50~100)."""
import pytest

from services import reading_progress_service as rps
from services.settings_service import SettingsService


@pytest.fixture(autouse=True)
def clear_cache():
    rps.invalidate_book_complete_percent()
    yield
    rps.invalidate_book_complete_percent()


@pytest.mark.parametrize('value, expected', [
    ('95', 95), ('50', 50), ('100', 100), (' 80 ', 80),
    ('49', None), ('101', None), ('', None), ('abc', None), (None, None), ('90.5', None),
])
def test_parse_book_complete_percent(value, expected):
    assert rps.parse_book_complete_percent(value) == expected


def test_default_is_95_when_unset_or_invalid(monkeypatch):
    monkeypatch.setattr(SettingsService, 'get_effective', staticmethod(lambda key, user_id=None, default='': ''))
    assert rps.get_book_complete_percent(1) == 95
    rps.invalidate_book_complete_percent()
    monkeypatch.setattr(SettingsService, 'get_effective', staticmethod(lambda key, user_id=None, default='': '10'))
    assert rps.get_book_complete_percent(1) == 95


def test_user_value_is_used_and_cached_until_invalidated(monkeypatch):
    calls = []
    values = {'v': '100'}

    def fake(key, user_id=None, default=''):
        calls.append((key, user_id))
        return values['v']

    monkeypatch.setattr(SettingsService, 'get_effective', staticmethod(fake))
    assert rps.get_book_complete_percent(7) == 100
    values['v'] = '80'
    assert rps.get_book_complete_percent(7) == 100  # 캐시
    assert calls == [('BOOK_COMPLETE_PERCENT', 7)]
    rps.invalidate_book_complete_percent(7)
    assert rps.get_book_complete_percent(7) == 80
