import time

_GENRE_CACHE = {}
_TAG_CACHE = {}
_CACHE_TTL = 30.0  # 30초 동안 인메모리 초고속 캐싱

class LibraryService:
    @staticmethod
    def get_media_tags(db_type, library_id=None):
        now = time.time()
        cache_key = f"{db_type}:{library_id}"
        if cache_key in _TAG_CACHE:
            ts, val = _TAG_CACHE[cache_key]
            if now - ts < _CACHE_TTL:
                return val

        tags_raw = BookRepository.get_media_tags(db_type, library_id)

        unique_tags = set()
        for r in tags_raw:
            if r:
                for tag in str(r).split(','):
                    clean_tag = tag.strip()
                    if clean_tag:
                        unique_tags.add(clean_tag)

        result = sorted(unique_tags)
        _TAG_CACHE[cache_key] = (now, result)
        return result

    @staticmethod
    def get_media_genres(db_type, library_id=None):
        now = time.time()
        cache_key = f"{db_type}:{library_id}"
        if cache_key in _GENRE_CACHE:
            ts, val = _GENRE_CACHE[cache_key]
            if now - ts < _CACHE_TTL:
                return val

        genres_raw = BookRepository.get_media_genres(db_type, library_id)

        unique_genres = set()
        for r in genres_raw:
            if r:
                for genre in str(r).split(','):
                    clean_genre = genre.strip()
                    if clean_genre:
                        unique_genres.add(clean_genre)

        result = sorted(unique_genres)
        _GENRE_CACHE[cache_key] = (now, result)
        return result
