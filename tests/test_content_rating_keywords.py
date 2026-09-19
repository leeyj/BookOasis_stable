from unittest.mock import patch

from services import series_service
from services.content_rating_service import ContentRatingService


def _row(book_id, genre='', tags='', books_lv=None):
    return {
        'id': book_id, 'library_id': 1, 'series_name': f'시리즈 {book_id}', 'title': f'시리즈 {book_id} 1권',
        'title_alias': '', 'series_alias': '', 'author': '', 'file_path': f'/lib/s{book_id}/1.cbz',
        'file_format': 'cbz', 'cover_image': '', 'cover_updated_at': None, 'cover_align': 'center',
        'created_at': '2026-01-01 00:00:00', 'is_favorite': 0, 'metadata_locked': 0,
        'genre': genre, 'tags': tags, 'books_lv': books_lv, 'publication_status': '',
        'series_book_count': 1, 'series_latest_added': '2026-01-01 00:00:00', 'has_metadata': None,
    }


def test_explicit_keywords_skip_the_settings_lookup():
    with patch('services.content_rating_service.SettingsService.get') as get:
        level = ContentRatingService.compute_effective_level(None, '로맨스', '', ['로맨스'])

    assert level == 18
    get.assert_not_called()


def test_omitted_keywords_still_read_the_setting_like_before():
    with patch('services.content_rating_service.SettingsService.get', return_value='로맨스, 성인') as get:
        assert ContentRatingService.compute_effective_level(None, '로맨스', '') == 18
        assert ContentRatingService.compute_effective_level(None, '판타지', '') == 0

    assert get.call_count == 2


def test_empty_keyword_list_means_no_match_and_no_lookup():
    with patch('services.content_rating_service.SettingsService.get') as get:
        assert ContentRatingService.compute_effective_level(None, '로맨스', '', []) == 0

    get.assert_not_called()


def test_build_series_entries_reads_adult_keywords_once_for_all_series():
    rows = [_row(i, genre='로맨스' if i % 2 else '판타지') for i in range(1, 41)]

    with patch('services.content_rating_service.SettingsService.get', return_value='로맨스') as get:
        entries = series_service._build_series_entries('general', rows)

    # 표지 처리 등 다른 코드가 읽는 설정은 제외하고, 성인 키워드 조회만 센다.
    keyword_reads = [c for c in get.call_args_list if c.args and c.args[0] == 'ADULT_GENRE_TAG_KEYWORDS']
    assert len(keyword_reads) == 1
    levels = {entry['series_name']: entry['content_rating_level'] for entry in entries}
    assert levels['시리즈 1'] == 18  # 로맨스 -> 키워드 매치로 등급 상향
    assert levels['시리즈 2'] == 0
