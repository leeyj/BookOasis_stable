# -*- coding: utf-8 -*-
"""
music_itunes.py - 음악 앨범 정보 조회 샘플 플러그인 (iTunes Search API, 키 불필요)

lookup_music_album 계약(BookOasis 2.8.4+)의 참조 구현이다. 오디오북 세션의 '음악' 카테고리에서
album.yaml이 없는 앨범을 코어가 스캔 뒤 백그라운드로 천천히 물어보면, iTunes에서 앨범을 찾아
아티스트/발매 연도/장르/커버(600px)를 돌려준다. 코어는 이 값을 앨범의 빈 칸에만 보여 준다.

- 폴더 이름의 '[2008.01.17 정규앨범] ' 같은 앞머리와 '(Digital Single)' 같은 꼬리는 떼고 검색한다.
- 아티스트를 알면 같은 아티스트 결과만 받는다. 제목이 충분히 비슷하지 않으면 못 찾음(None)으로 둔다.
- iTunes Search API는 분당 약 20회로 제한된다. 코어가 앨범 사이에 쉬고(기본 5초), 아티스트 별칭은 기억해 호출을 줄인다.
"""
import difflib
import json
import re
import urllib.parse
import urllib.request

from plugins.metadata.base import BaseMetadataProvider

_SEARCH_URL = 'https://itunes.apple.com/search'
_HEADERS = {'User-Agent': 'BookOasis-music-itunes/1.0'}
_LEADING_BRACKETS_RE = re.compile(r'^(?:\s*[\[\(【][^\]\)】]*[\]\)】]\s*)+')
# 꼬리: 대괄호 묶음은 전부([MQA], [XRCD], [FLAC]), 괄호는 알려진 잡음 단어나 연도가 든 것만
# ('(Digital Single)', '(2011)', '(JVC, 2010)') - '(Feat. ...)' 같은 제목 일부는 남긴다.
_TRAILING_NOISE_RE = re.compile(
    r'\s*(?:\[[^\]]*\]|\((?:digital single|single|ep|flac|mp3|\d{2,4}\s*k(?:bps)?|remaster(?:ed)?|[^()]*\b(?:19|20)\d{2})\))\s*$',
    re.IGNORECASE)
_ITUNES_SUFFIX_RE = re.compile(r'\s*-\s*(?:single|ep)\s*$', re.IGNORECASE)
_NORM_RE = re.compile(r'[\s\W_]+', re.UNICODE)
MIN_TITLE_SCORE = 0.6


def _norm(text):
    return _NORM_RE.sub('', str(text or '')).lower()


def clean_album_title(folder_name):
    """'[2008.01.17 정규앨범] Andy The First New Dream (Digital Single)' -> 'Andy The First New Dream'"""
    title = _LEADING_BRACKETS_RE.sub('', str(folder_name or '')).strip()
    previous = None
    while previous != title:
        previous = title
        title = _TRAILING_NOISE_RE.sub('', title).strip()
    return title


def _artist_matches(wanted_names, found):
    b = _norm(found)
    return any(a and b and (a in b or b in a) for a in (_norm(n) for n in wanted_names))


def pick_best(results, title, artists):
    """iTunes 앨범 결과 중 제목이 가장 비슷한 것(아티스트 이름을 알면 그중 하나와 같은 결과만). 기준 미달이면 None.
    artists: 아티스트 이름 목록(원래 이름 + 스토어 표기 별칭). 비어 있으면 아티스트를 따지지 않는다."""
    wanted = _norm(title)
    best, best_score = None, 0.0
    for item in results:
        name = _ITUNES_SUFFIX_RE.sub('', str(item.get('collectionName') or ''))
        if artists and not _artist_matches(artists, item.get('artistName')):
            continue
        score = difflib.SequenceMatcher(None, wanted, _norm(name)).ratio()
        if score > best_score:
            best, best_score = item, score
    return best if best is not None and best_score >= MIN_TITLE_SCORE else None


def to_lookup_result(item):
    artwork = str(item.get('artworkUrl100') or '')
    return {
        'artist': item.get('artistName') or None,
        'year': str(item.get('releaseDate') or '')[:4] or None,
        'genres': [item['primaryGenreName']] if item.get('primaryGenreName') else [],
        'cover_url': artwork.replace('100x100bb', '600x600bb') if artwork else None,
        'source_url': item.get('collectionViewUrl') or None,
    }


class MusicItunesMetadataProvider(BaseMetadataProvider):
    """album.yaml이 없는 음악 앨범의 아티스트/연도/장르/커버를 iTunes에서 찾아 준다."""

    id = "music_itunes"
    name = "음악 앨범 정보 (iTunes)"
    is_searchable = False
    config_schema = [
        {
            "key": "COUNTRY",
            "label": "iTunes 스토어 국가 코드 (기본 US - KR 스토어는 앨범 검색 결과가 없음)",
            "type": "text",
            "required": False,
        },
    ]

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 도서 메타데이터 적용을 지원하지 않습니다."

    def _country(self):
        try:
            config = self.get_plugin_config('audiobook', default={}) or {}
        except Exception:
            config = {}
        country = str(config.get('COUNTRY') or 'US').strip().upper()
        return country if re.fullmatch(r'[A-Z]{2}', country) else 'US'

    def _search(self, term, entity, limit):
        query = urllib.parse.urlencode({'term': term, 'entity': entity, 'country': self._country(), 'limit': limit})
        req = urllib.request.Request(f'{_SEARCH_URL}?{query}', headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8')).get('results') or []

    def _search_albums(self, term):
        return self._search(term, 'album', 15)

    _alias_cache = {}

    def _store_artist_names(self, artist):
        """'앤디' -> ['SHINHWA', 'ANDY', ...]: 스토어가 영문 표기를 쓰는 경우의 별칭 후보 (아티스트 검색 상위 5개).
        1위가 소속 그룹일 때가 있어(앤디 → SHINHWA) 한 개만 믿지 않는다. 제목 일치가 함께 필요하므로
        후보가 넓어도 다른 가수의 같은 제목 앨범은 걸러진다. 아티스트별로 기억해 API 호출을 줄인다."""
        key = _norm(artist)
        if key not in self._alias_cache:
            hits = self._search(artist, 'musicArtist', 5)
            self._alias_cache[key] = [h.get('artistName') for h in hits if h.get('artistName')]
        return self._alias_cache[key]

    def lookup_music_album(self, db_type, context):
        title = clean_album_title(context.get('folder_name'))
        artist = str(context.get('artist') or '').strip()
        if not title:
            return None
        if not artist and ' - ' in title:
            # 태그도 album.yaml도 없는 'Artist - Album' 폴더
            artist, title = [part.strip() for part in title.split(' - ', 1)]
        results = self._search_albums(f'{artist} {title}'.strip())
        artists = [artist] if artist else []
        best = pick_best(results, title, artists)
        if best is None and artist:
            # 결과의 아티스트 표기가 다르면(앤디 → ANDY) 스토어 표기 후보로 다시 비교 (결과가 없으면 한 번 더 검색)
            aliases = [a for a in self._store_artist_names(artist) if _norm(a) != _norm(artist)]
            if aliases:
                if not results:
                    results = self._search_albums(f'{aliases[0]} {title}')
                best = pick_best(results, title, artists + aliases)
        return to_lookup_result(best) if best else None
