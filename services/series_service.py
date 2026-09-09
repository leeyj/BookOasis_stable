# -*- coding: utf-8 -*-
import os
import re
import hashlib
import json
import time
from utils.cover_helper import get_cover_image_with_t, resolve_series_cover
from repositories.series_repository import SeriesRepository

_CHOSEONG = [
    'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ',
    'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ',
    'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ',
]

_LEADING_TAG_RE = re.compile(r'^\s*(?:(?:\[[^\]]+\]|\{[^}]+\})\s*)+')


def _strip_leading_bracket_tags(value):
    """static/js/series_display.js의 stripLeadingBracketTags와 동일 규칙.

    정렬/초성판정 모두 이 결과를 기준으로 삼아야 한다 - 둘 중 하나만 태그를 떼면
    정렬 순서와 판정 기준이 어긋나 초성 바로가기가 엉뚱한 위치로 튄다(대괄호 `[`가
    영문 Z와 한글 사이 코드포인트라 태그 있는 제목들이 그 사이에 무더기로 끼어듦)."""
    raw = str(value or '').strip()
    if not raw:
        return ''
    stripped = _LEADING_TAG_RE.sub('', raw).strip()
    return stripped or raw


def _get_initial(text):
    """static/js/index_scrollbar.js의 getInitial()과 동일한 초성/알파벳 분류 규칙."""
    text = (text or '').strip()
    if not text:
        return '#'
    ch = text[0]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return _CHOSEONG[(code - 0xAC00) // 588]
    if 0x3131 <= code <= 0x314E:
        return ch
    if ('a' <= ch <= 'z') or ('A' <= ch <= 'Z'):
        return ch.upper()
    return '#'

def _comparison_dir_for_book(file_path, file_format):
    normalized = str(file_path or '').replace('\\', '/')
    if not normalized:
        return ''
    if str(file_format or '').lower() == 'imgdir' and normalized.endswith('/__folder__.imgdir'):
        return os.path.dirname(os.path.dirname(file_path))
    return os.path.dirname(file_path)


def _normalize_library_id(library_id):
    if isinstance(library_id, str):
        library_id = library_id.strip()
        token = library_id.lower()
        if token in ('all', 'favorite', 'history', 'home'):
            return token
    try:
        if library_id is not None and library_id not in ('all', 'favorite', 'history', 'home'):
            return int(library_id)
    except (ValueError, TypeError):
        pass
    return library_id


def _build_series_entries(db_type, rows):
    groups = {}
    order = []

    for row in rows:
        series_name = row['series_name'] or '기타 단행본'
        comp_dir = _comparison_dir_for_book(row['file_path'], row['file_format'])
        key = (row['library_id'], series_name, comp_dir)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    from services.cover_storage_service import get_covers_dir
    covers_dir = get_covers_dir()

    entries = []
    for key in order:
        lib_id, series_name, comp_dir = key
        books = groups[key]
        representative = min(books, key=lambda r: r['id'])

        first_with_cover = next((b for b in books if b['cover_image']), None)
        db_cover = first_with_cover['cover_image'] if first_with_cover else None
        updated_at = first_with_cover['cover_updated_at'] if first_with_cover else None
        # 카드에 실제로 뜨는 커버(first_with_cover)의 정렬값을 써야 그리드에서도
        # 상세 페이지 권 목록에서 설정한 것과 동일하게 보인다.
        cover_align = (first_with_cover or {}).get('cover_align') or 'center'

        final_cover = resolve_series_cover(
            series_name=series_name,
            lib_id=lib_id,
            db_cover=db_cover,
            covers_dir=covers_dir,
            conn=None,
            candidates_rows=books,
            allow_series_cover=False,
            db_type=db_type
        )



        latest_added = max((b['created_at'] for b in books if b['created_at']), default='')
        any_favorite = 1 if any((b['is_favorite'] or 0) == 1 for b in books) else 0
        any_locked = 1 if any((b.get('metadata_locked') or 0) == 1 for b in books) else 0
        author = next((b['author'] for b in books if b['author']), '')
        genre = next((b['genre'] for b in books if b['genre']), '')
        tags = next((b['tags'] for b in books if b['tags']), '')
        series_alias = next((b['series_alias'] for b in books if b.get('series_alias')), '')
        total_tracks = 0
        is_completed = 0
        if db_type in ('audiobook', 'video'):
            total_tracks = max((int(b.get('total_tracks') or 0) for b in books), default=0)
            is_completed = 1 if any(int(b.get('is_completed') or 0) == 1 for b in books) else 0
        series_key = hashlib.md5(f"{lib_id}|{series_name}|{comp_dir}".encode('utf-8')).hexdigest()[:16]

        book_count = sum(int(b.get('series_book_count') or b.get('book_count') or 1) for b in books)

        entries.append({
            'series_key': f"{lib_id}:{series_key}",
            'series_name': series_name,
            'series_alias': series_alias,
            'display_name': series_alias if series_alias else series_name,
            'representative_title': representative.get('title_alias') or representative['title'] or '',
            'author': author,
            'book_count': book_count,
            'total_tracks': total_tracks,
            'is_completed': is_completed,
            'cover_image': get_cover_image_with_t(final_cover, updated_at),
            'cover_align': cover_align,
            'is_favorite': any_favorite,
            'metadata_locked': any_locked,
            'latest_added': latest_added,
            'representative_book_id': representative['id'],
            'library_id': lib_id,
            'genre': genre,
            'tags': tags,
            'anchor_dir': comp_dir,
        })

    return entries


def _build_author_entries(db_type, rows):
    """작가별 모음 그리드용 엔트리 생성. 정규화된 작가명(normalize_author_key)으로 묶고,
    카드 렌더링은 기존 시리즈 카드(createBookCard)를 그대로 재사용할 수 있도록
    _build_series_entries와 동일한 필드 이름을 채운다."""
    from repositories.series_search_query import normalize_author_key

    groups = {}
    order = []

    for row in rows:
        author_key = normalize_author_key(row['author'])
        if not author_key:
            continue
        if author_key not in groups:
            groups[author_key] = []
            order.append(author_key)
        groups[author_key].append(row)

    entries = []
    for author_key in order:
        books = groups[author_key]
        display_author = next((b['author'] for b in books if b['author']), '') or author_key

        first_with_cover = next((b for b in books if b['cover_image']), None)
        cover_image = first_with_cover['cover_image'] if first_with_cover else None
        updated_at = first_with_cover['cover_updated_at'] if first_with_cover else None

        representative = min(books, key=lambda r: r['id'])
        latest_added = max((b['created_at'] for b in books if b['created_at']), default='')
        any_favorite = 1 if any((b['is_favorite'] or 0) == 1 for b in books) else 0
        any_locked = 1 if any((b.get('metadata_locked') or 0) == 1 for b in books) else 0
        book_count = sum(int(b.get('series_book_count') or b.get('book_count') or 1) for b in books)

        # 카드 제목에 "이현세 (22)"처럼 붙일 시리즈 수(권수가 아니라 시리즈 개수) —
        # _build_series_entries와 동일한 (library_id, series_name, comp_dir) 그룹핑 기준 재사용.
        distinct_series = {
            (b['library_id'], b['series_name'] or '기타 단행본', _comparison_dir_for_book(b['file_path'], b['file_format']))
            for b in books
        }
        series_count = len(distinct_series)

        entries.append({
            'series_key': f"author:{author_key}",
            'series_name': display_author,
            'series_alias': '',
            'display_name': f"{display_author} ({series_count})",
            'representative_title': display_author,
            'author': display_author,
            'book_count': book_count,
            'cover_image': get_cover_image_with_t(cover_image, updated_at),
            'is_favorite': any_favorite,
            'metadata_locked': any_locked,
            'latest_added': latest_added,
            'representative_book_id': representative['id'],
            'library_id': representative['library_id'],
            'genre': '',
            'tags': '',
            'anchor_dir': '',
            'author_key': author_key,
            'is_author_group': True,
        })

    return entries


def _sort_entries(entries, sort='asc'):
    sort_key = (sort or 'asc').lower()
    if sort_key in ('asc', 'desc'):
        reverse = (sort_key == 'desc')
        entries.sort(
            key=lambda x: (
                _strip_leading_bracket_tags(x.get('series_name') or ''),
                _strip_leading_bracket_tags(x.get('representative_title') or ''),
            ),
            reverse=reverse,
        )
        return

    if sort_key == 'date_asc':
        entries.sort(key=lambda x: str(x.get('latest_added') or ''))
        return

    # default: latest first
    entries.sort(key=lambda x: str(x.get('latest_added') or ''), reverse=True)


_ALL_BOOKS_CACHE = {}
_ALL_BOOKS_CACHE_TTL = 60.0  # 60초 인메모리 캐싱
_LIST_QUERY_CACHE = {}
_LIST_QUERY_CACHE_TTL = 120.0
_TOTALS_CACHE = {}
_TOTALS_CACHE_TTL = 30.0
_TOTALS_REDIS_TTL = 300

# ── [크로스 프로세스 캐시 무효화 신호] ──
# 스캐너는 core.py의 start_scanner_worker_process()가 subprocess.Popen으로 띄우는
# 완전히 별도의 OS 프로세스라, 스캔이 끝나서 이 워커 프로세스 안에서 위 3개
# 전역 dict를 clear()해도 실제 요청을 받는 웹(Flask) 프로세스의 캐시는 그대로
# 남는다 - 이게 "스캔 직후 커버가 안 보이다가 재스캔하면 보인다"는 버그의 원인이었다.
# 그렇다고 캐시 자체(수천 건짜리 시리즈 목록)를 통째로 Redis에 올리면 Redis 미설정
# 배포(REDIS_URL 없음 - utils/redis_helper.py 참고)에서는 무효화가 여전히 안 되고,
# Redis가 있어도 매 요청마다 큰 payload 직렬화 비용만 늘어난다. 대신 "값이 바뀌었다"는
# 신호(epoch)만 아주 저렴하게(Redis 있으면 Redis, 없으면 항상 존재하는 settings
# 테이블) 공유하고, 각 웹 프로세스가 몇 초에 한 번씩만 그 신호를 확인해 필요할 때만
# 자기 로컬 캐시를 비운다.
_BOOKS_CACHE_EPOCH_CHECK_INTERVAL = 3.0
_local_epoch_seen = {}
_local_epoch_checked_at = {}


def _books_cache_epoch_settings_key(db_type):
    return f'BOOKS_CACHE_EPOCH_{db_type}'


def _read_shared_books_cache_epoch(db_type):
    """Redis가 있으면 Redis에서, 없으면 항상 단일 general DB로 고정되는 settings
    테이블(SettingsRepository 참고)에서 공유 epoch 값을 읽는다."""
    try:
        from utils.redis_helper import redis_get
        val = redis_get(f'cache:books_epoch:{db_type}')
        if val is not None:
            return val
    except Exception:
        pass
    try:
        from services.settings_service import SettingsService
        return SettingsService.get(_books_cache_epoch_settings_key(db_type), '') or ''
    except Exception:
        return ''


def _bump_shared_books_cache_epoch(db_type):
    """스캐너 워커 등 다른 프로세스에서 도서 목록이 바뀌었음을 알릴 때 호출한다."""
    new_epoch = str(time.time())
    try:
        from utils.redis_helper import redis_set
        redis_set(f'cache:books_epoch:{db_type}', new_epoch, ex=86400)
    except Exception:
        pass
    try:
        from services.settings_service import SettingsService
        SettingsService.set(_books_cache_epoch_settings_key(db_type), new_epoch)
    except Exception:
        pass
    _local_epoch_seen[db_type] = new_epoch
    _local_epoch_checked_at[db_type] = time.time()


def _sync_local_books_cache_with_shared_epoch(db_type):
    """이 프로세스의 로컬 캐시가 다른 프로세스의 무효화를 놓치지 않았는지 확인한다.
    매 요청마다 확인하면 로컬 캐시를 두는 의미가 없어지므로
    _BOOKS_CACHE_EPOCH_CHECK_INTERVAL 간격으로만 저렴하게 확인(스로틀링)한다."""
    now = time.time()
    if now - _local_epoch_checked_at.get(db_type, 0.0) < _BOOKS_CACHE_EPOCH_CHECK_INTERVAL:
        return
    _local_epoch_checked_at[db_type] = now
    current_epoch = _read_shared_books_cache_epoch(db_type)
    seen_epoch = _local_epoch_seen.get(db_type)
    if seen_epoch is not None and seen_epoch != current_epoch:
        _ALL_BOOKS_CACHE.clear()
        _LIST_QUERY_CACHE.clear()
        _TOTALS_CACHE.clear()
    _local_epoch_seen[db_type] = current_epoch


class SeriesService:
    @staticmethod
    def invalidate_all_books_cache(db_type=None):
        """도서 목록 캐시를 비운다. db_type을 넘기면 다른 프로세스(스캐너 워커 등)에도
        전달되도록 공유 epoch를 갱신한다 - 위 "크로스 프로세스 캐시 무효화 신호" 참고."""
        global _ALL_BOOKS_CACHE, _LIST_QUERY_CACHE, _TOTALS_CACHE
        _ALL_BOOKS_CACHE.clear()
        _LIST_QUERY_CACHE.clear()
        _TOTALS_CACHE.clear()
        try:
            from utils.redis_helper import redis_delete_pattern
            redis_delete_pattern('cache:series_totals:*')
        except Exception:
            pass
        if db_type:
            _bump_shared_books_cache_epoch(db_type)

    @staticmethod
    def get_books_list(db_type, library_id, page, limit, search_query, sort='asc', genre_filters=None, tag_filters=None, user_id=None, role=None, group_by=None, author_key=None):
        import time
        t0 = time.perf_counter()
        _sync_local_books_cache_with_shared_epoch(db_type)
        library_id = _normalize_library_id(library_id)
        favorite_only = library_id == 'favorite'
        normalized_genres = [str(v).strip() for v in (genre_filters or []) if str(v).strip()]
        normalized_tags = [str(v).strip() for v in (tag_filters or []) if str(v).strip()]
        group_by = (group_by or '').strip().lower()
        author_key = (author_key or '').strip()

        offset = max(0, (page - 1) * limit)
        # 작가별 그룹핑/작가 드릴다운은 인덱스 없는 파이썬 그룹핑이라 항상 전체스캔 경로를 탄다.
        requires_full_scan = bool(search_query) or (sort not in ('asc', 'desc')) or bool(group_by) or bool(author_key)

        now = time.time()
        cache_key = (
            db_type,
            library_id,
            str(search_query or ''),
            str(sort or 'asc'),
            tuple(normalized_genres),
            tuple(normalized_tags),
            int(user_id) if user_id else 0,
            str(role or ''),
            group_by,
            author_key,
        )

        if not requires_full_scan:
            # find_jump_position()이 남긴 신선한 전체스캔 캐시가 있으면 그걸 그대로 슬라이스해서
            # 쓴다 - _sort_entries()가 대괄호 태그를 뗀 제목 기준으로 정렬하는데, 아래 SQL
            # ORDER BY는 원본 제목 기준이라 서로 순서가 다르다. 점프 직후 이 캐시를 안 쓰면
            # 초성 바로가기가 계산해준 page/offset과 실제로 렌더링되는 카드가 어긋난다.
            cached = _LIST_QUERY_CACHE.get(cache_key)
            if cached and (now - cached[0] < _LIST_QUERY_CACHE_TTL):
                entries = cached[1]
                return entries[offset:offset + limit + 1]
        else:
            cached = _LIST_QUERY_CACHE.get(cache_key)
            if cached and (now - cached[0] < _LIST_QUERY_CACHE_TTL):
                entries = cached[1]
                paged = entries[offset:offset + limit + 1]
                t_cached = time.perf_counter()
                print(f"[PERF-PROFILE] get_books_list(lib={library_id}, page={page}) QUERY-CACHE HIT ({len(entries)}entries): {(t_cached-t0)*1000:.1f}ms")
                return paged

            t1 = time.perf_counter()
            rows = SeriesRepository.fetch_books_for_grouping(
                db_type,
                library_id,
                # author_key 드릴다운은 정규화 매칭이라 자유텍스트 검색(LIKE)은 적용하지 않고
                # 스코프(라이브러리/즐겨찾기/장르/태그) 안 전체 행을 가져와 파이썬에서 직접 거른다.
                search_query=('' if author_key else (search_query or '')),
                favorite_only=favorite_only,
                genre_filters=normalized_genres,
                tag_filters=normalized_tags,
                user_id=user_id,
                role=role,
                limit=None,
                offset=None
            )
            t2 = time.perf_counter()

            if author_key:
                from repositories.series_search_query import normalize_author_key
                rows = [r for r in rows if normalize_author_key(r['author']) == author_key]
                entries = _build_series_entries(db_type, rows)
            elif group_by == 'author':
                entries = _build_author_entries(db_type, rows)
            else:
                entries = _build_series_entries(db_type, rows)
            t3 = time.perf_counter()

            _sort_entries(entries, sort=sort)
            t4 = time.perf_counter()

            _LIST_QUERY_CACHE[cache_key] = (now, entries)
            paged = entries[offset:offset + limit + 1]
            print(f"[PERF-PROFILE] get_books_list(lib={library_id}, page={page}) FULL-SCAN CACHE BUILD TOTAL: {(t4-t0)*1000:.1f}ms | SQL-Fetch({len(rows)}rows): {(t2-t1)*1000:.1f}ms | BuildSeries({len(entries)}entries): {(t3-t2)*1000:.1f}ms | Sort: {(t4-t3)*1000:.1f}ms")
            return paged

        sql_limit = limit + 1
        sql_offset = offset

        t1 = time.perf_counter()
        rows = SeriesRepository.fetch_books_for_grouping(
            db_type,
            library_id,
            search_query=search_query or '',
            favorite_only=favorite_only,
            genre_filters=normalized_genres,
            tag_filters=normalized_tags,
            user_id=user_id,
            role=role,
            limit=sql_limit,
            offset=sql_offset,
            sort=sort
        )
        t2 = time.perf_counter()

        entries = _build_series_entries(db_type, rows)
        t3 = time.perf_counter()

        _sort_entries(entries, sort=sort)
        t4 = time.perf_counter()

        paged = entries if sql_limit is not None else entries[offset:offset + limit + 1]
        
        print(f"[PERF-PROFILE] get_books_list(lib={library_id}, page={page}) TOTAL: {(t4-t0)*1000:.1f}ms | SQL-Fetch({len(rows)}rows): {(t2-t1)*1000:.1f}ms | BuildSeries({len(entries)}entries): {(t3-t2)*1000:.1f}ms | Sort: {(t4-t3)*1000:.1f}ms")
        return paged

    @staticmethod
    def find_jump_position(db_type, library_id, search_query, sort, target_char, limit,
                            genre_filters=None, tag_filters=None, user_id=None, role=None):
        """
        가나다(초성) 바로가기: 전체 목록을 동일한 정렬 기준으로 구성한 뒤 target_char로
        시작하는 첫 항목의 절대 인덱스를 찾아 페이지/오프셋으로 환산합니다.
        get_books_list()의 전체스캔(full-scan) 경로와 동일한 fetch+build+sort 로직 및
        캐시(_LIST_QUERY_CACHE)를 재사용하여, 반복 점프 시 재계산 비용을 없앱니다.
        """
        import time
        _sync_local_books_cache_with_shared_epoch(db_type)
        library_id = _normalize_library_id(library_id)
        favorite_only = library_id == 'favorite'
        normalized_genres = [str(v).strip() for v in (genre_filters or []) if str(v).strip()]
        normalized_tags = [str(v).strip() for v in (tag_filters or []) if str(v).strip()]
        sort_key = (sort or 'asc').lower()
        if sort_key not in ('asc', 'desc'):
            sort_key = 'asc'

        now = time.time()
        cache_key = (
            db_type,
            library_id,
            str(search_query or ''),
            sort_key,
            tuple(normalized_genres),
            tuple(normalized_tags),
            int(user_id) if user_id else 0,
            str(role or ''),
        )
        cached = _LIST_QUERY_CACHE.get(cache_key)
        if cached and (now - cached[0] < _LIST_QUERY_CACHE_TTL):
            entries = cached[1]
        else:
            rows = SeriesRepository.fetch_books_for_grouping(
                db_type,
                library_id,
                search_query=search_query or '',
                favorite_only=favorite_only,
                genre_filters=normalized_genres,
                tag_filters=normalized_tags,
                user_id=user_id,
                role=role,
                limit=None,
                offset=None
            )
            entries = _build_series_entries(db_type, rows)
            _sort_entries(entries, sort=sort_key)
            _LIST_QUERY_CACHE[cache_key] = (now, entries)

        target = str(target_char or '').strip()
        total = len(entries)
        found_index = -1
        for idx, entry in enumerate(entries):
            # _sort_entries()가 대괄호 태그를 뗀 제목 기준으로 정렬하므로, 여기서도 반드시
            # 같은 기준(뗀 제목)으로 초성을 판정해야 한다. 판정 기준이 정렬 기준과 어긋나면
            # 계산된 page/offset이 실제 그리드가 보여주는 위치와 어긋나서 "엉뚱한 곳으로
            # 점프"하게 된다 ([태그] 접두사가 흔한 영상 강좌 제목에서 특히 두드러짐 - '['는
            # 유니코드에서 영문 Z와 한글 사이에 끼어들어 정렬 순서를 깨뜨린다).
            title = _strip_leading_bracket_tags(entry.get('series_name') or entry.get('representative_title') or '')
            if _get_initial(title) == target:
                found_index = idx
                break

        if found_index == -1:
            return {'found': False, 'total': total}

        safe_limit = max(1, int(limit or 1))
        return {
            'found': True,
            'index': found_index,
            'page': (found_index // safe_limit) + 1,
            'offset_in_page': found_index % safe_limit,
            'total': total,
        }

    @staticmethod
    def get_books_totals(db_type, library_id, search_query='', genre_filters=None, tag_filters=None, user_id=None, role=None):
        import time
        _sync_local_books_cache_with_shared_epoch(db_type)
        library_id = _normalize_library_id(library_id)
        favorite_only = library_id == 'favorite'
        normalized_genres = [str(value).strip() for value in (genre_filters or []) if str(value).strip()]
        normalized_tags = [str(value).strip() for value in (tag_filters or []) if str(value).strip()]
        cache_payload = json.dumps({
            'db_type': db_type,
            'library_id': library_id,
            'search': str(search_query or ''),
            'genres': normalized_genres,
            'tags': normalized_tags,
            'user_id': int(user_id) if user_id else 0,
            'role': str(role or ''),
        }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        cache_digest = hashlib.sha256(cache_payload.encode('utf-8')).hexdigest()
        cache_key = f"cache:series_totals:{db_type}:{cache_digest}"

        redis_available = False
        try:
            from utils.redis_helper import get_redis_client, redis_get
            redis_available = get_redis_client() is not None
            if redis_available:
                cached_json = redis_get(cache_key)
                if cached_json:
                    cached_totals = json.loads(cached_json)
                    return {
                        'total_series_count': int(cached_totals.get('total_series_count') or 0),
                        'total_book_count': int(cached_totals.get('total_book_count') or 0),
                    }
        except Exception:
            redis_available = False

        now = time.time()
        if not redis_available:
            cached = _TOTALS_CACHE.get(cache_key)
            if cached and now - cached[0] < _TOTALS_CACHE_TTL:
                return cached[1]

        totals = SeriesRepository.fetch_grouping_totals(
            db_type,
            library_id,
            search_query=search_query or '',
            favorite_only=favorite_only,
            genre_filters=normalized_genres,
            tag_filters=normalized_tags,
            user_id=user_id,
            role=role,
        )

        if redis_available:
            try:
                from utils.redis_helper import redis_set
                redis_set(cache_key, json.dumps(totals, ensure_ascii=False), ex=_TOTALS_REDIS_TTL)
            except Exception:
                pass
        else:
            _TOTALS_CACHE[cache_key] = (now, totals)
        return totals

    @staticmethod
    def get_all_books_list(db_type, library_id, user_id=None, role=None):
        """Kavita 방식의 선로드를 위해 특정 라이브러리의 전체 시리즈 목록을 페이징 없이 경량 조회"""
        import time
        t0 = time.perf_counter()
        _sync_local_books_cache_with_shared_epoch(db_type)
        library_id = _normalize_library_id(library_id)
        favorite_only = library_id == 'favorite'
        
        now = time.time()
        # 즐겨찾기 카테고리는 유저별 개별 데이터이므로 글로벌 통캐시에서 제외하거나 유저 키 적용
        cache_key = f"user:{user_id}:{db_type}:{library_id}" if favorite_only else f"global:{db_type}:{library_id}"
        if not favorite_only and cache_key in _ALL_BOOKS_CACHE:
            cache_ts, cached_entries = _ALL_BOOKS_CACHE[cache_key]
            if now - cache_ts < 300.0:
                print(f"[PERF-PROFILE] get_all_books_list(lib={library_id}) GLOBAL IN-MEMORY CACHE HIT! ({len(cached_entries)} entries) - {(time.perf_counter()-t0)*1000:.1f}ms")
                return cached_entries

        t1 = time.perf_counter()
        rows = SeriesRepository.fetch_books_for_grouping(
            db_type,
            library_id,
            search_query='',
            favorite_only=favorite_only,
            user_id=user_id,
            role=role
        )
        t2 = time.perf_counter()

        entries = _build_series_entries(db_type, rows)
        t3 = time.perf_counter()

        _sort_entries(entries, sort='asc')
        t4 = time.perf_counter()

        _ALL_BOOKS_CACHE[cache_key] = (now, entries)
        print(f"[PERF-PROFILE] get_all_books_list(lib={library_id}) TOTAL: {(t4-t0)*1000:.1f}ms | SQL-Fetch({len(rows)}rows): {(t2-t1)*1000:.1f}ms | BuildSeries({len(entries)}entries): {(t3-t2)*1000:.1f}ms | Sort: {(t4-t3)*1000:.1f}ms")
        return entries
