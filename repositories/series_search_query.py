import re

AUTHOR_PREFIX = '작가:'
TOPIC_PREFIX = '주제:'
COVER_ARTIST_PREFIX = '그림작가:'
COVER_ARTIST_PREFIX_ALIASES = ('cover_artist:',)


def parse_series_search_query(search_query):
    query = str(search_query or '').strip()
    for prefix in (COVER_ARTIST_PREFIX, *COVER_ARTIST_PREFIX_ALIASES):
        if query.lower().startswith(prefix.lower()):
            return 'cover_artist', query[len(prefix):].strip()
    if query.startswith(TOPIC_PREFIX):
        return 'topic', query[len(TOPIC_PREFIX):].strip()
    if query.startswith(AUTHOR_PREFIX):
        return 'author', query[len(AUTHOR_PREFIX):].strip()
    return 'title', query


def normalize_author_key(author):
    """작가별 모음 그룹핑/드릴다운 필터용 정규화 키.
    공백(선행/후행/중간, 전각·NBSP 포함, \\s는 유니코드 기준) 전부 제거 + 대소문자 무시.
    공동저자 문자열("김 작가, 이 작가")은 분리하지 않고 그대로 하나의 키로 취급한다."""
    return re.sub(r'\s+', '', str(author or '')).strip().lower()