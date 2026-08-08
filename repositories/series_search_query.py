AUTHOR_PREFIX = '작가:'


def parse_series_search_query(search_query):
    query = str(search_query or '').strip()
    if query.startswith(AUTHOR_PREFIX):
        return 'author', query[len(AUTHOR_PREFIX):].strip()
    return 'title', query