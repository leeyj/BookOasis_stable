# -*- coding: utf-8 -*-
import hashlib
import io
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
import urllib.request

from PIL import Image

from plugins.metadata.base import BaseMetadataProvider

_NAVER_SEARCH_API = "https://comic.naver.com/api/search/all"
# 카카오페이지 웹이 쓰는 BFF 검색 API. 웹툰/웹소설/만화를 모두 포함하고, 구 다음웹툰(카카오웹툰)
# 작품도 상당수 있지만 전부는 아니다(예: 50픽셀 데이즈). Referer가 없으면 403을 돌려준다.
_KAKAOPAGE_SEARCH_API = "https://bff-page.kakao.com/api/gateway/api/v2/search/series"
_KAKAOPAGE_IMAGE_URL = "https://page-images.kakaoentcdn.com/download/resource?kid="
_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
_KAKAOPAGE_HEADERS = {**_HEADERS, 'Referer': 'https://page.kakao.com/'}
# 카카오웹툰 검색 결과에는 표지가 없어서 작품별 상세 API를 한 번씩 더 불러야 한다.
# 이미지 CDN은 확장자 없이 요청하면 404라 '.webp'를 붙인다.
_KAKAOWEBTOON_SEARCH_API = "https://gateway-kw.kakao.com/search/v2/content"
_KAKAOWEBTOON_DETAIL_API = "https://gateway-kw.kakao.com/decorator/v2/decorator/contents/"
_KAKAOWEBTOON_HEADERS = {**_HEADERS, 'Accept-Language': 'ko'}
_KAKAOWEBTOON_LIMIT = 10
# 판매 중지 작품은 검색 API에서 빠지지만 상세 API로는 조회된다. 작품 URL을 검색어로 받으면 바로 조회한다.
_KAKAOWEBTOON_URL_RE = re.compile(r'webtoon\.kakao\.com/content/[^/?#]*/(\d+)')


def _fetch_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


class WebtoonSearchMetadataProvider(BaseMetadataProvider):
    """네이버웹툰/카카오페이지/카카오웹툰 공개 검색 API(로그인/키 불필요)로 시리즈를 찾아 표지를 적용합니다.

    웹툰/컷툰은 권별 표지가 따로 의미가 없는데도 스캐너가 각 회차 CBZ의 첫 페이지를
    표지로 자동 추출해버려서, 시리즈 대표 이미지를 매 권 수동으로 올려야 하는 반복
    작업이 생긴다. apply()는 기존 단건 검색/적용 UI를 그대로 쓰되, 선택된 표지를
    해당 book_id 하나가 아니라 같은 series_name의 모든 권에 한 번에 반영한다.

    카카오웹툰은 표지가 정사각형 공유 이미지뿐이라, 카카오페이지에 같은 웹툰이 있으면
    세로 표지가 있는 카카오페이지 결과만 남기고 카카오웹툰에만 있는 작품만 추가한다.
    """

    id = "webtoon_search"
    name = "웹툰 시리즈 표지 (네이버/카카오)"
    is_searchable = True
    config_schema = []

    def search(self, db_type, query):
        query = (query or '').strip()
        if not query:
            return []
        url_match = _KAKAOWEBTOON_URL_RE.search(query)
        if url_match:
            detail = self._fetch_kakaowebtoon_detail(url_match.group(1))
            result = self._kakaowebtoon_result(detail) if detail else None
            return [result] if result else []

        # 한 쪽 API가 죽어도 다른 쪽 결과는 보여준다.
        kakaopage = self._search_kakaopage(query)
        kakaopage_webtoons = {
            r['title'].replace(' ', '') for r in kakaopage if r['publisher'].startswith('카카오페이지 (웹툰')
        }
        results = self._search_naver(query) + kakaopage + self._search_kakaowebtoon(query, kakaopage_webtoons)

        # 네이버는 도전만화까지 느슨하게 매칭해서 그대로 이어 붙이면 카카오페이지의 정확한
        # 결과가 맨 뒤로 밀린다. 제목 일치도로만 안정 정렬해 각 소스 내부 순서는 유지한다.
        needle = query.replace(' ', '')

        def relevance(item):
            title = (item.get('title') or '').replace(' ', '')
            if title == needle:
                return 0
            if title.startswith(needle):
                return 1
            return 2 if needle in title else 3

        return sorted(results, key=relevance)

    def _search_kakaopage(self, query):
        params = {'keyword': query, 'category_uid': 0, 'page': 0, 'size': 25}
        try:
            data = _fetch_json(f"{_KAKAOPAGE_SEARCH_API}?{urllib.parse.urlencode(params)}", _KAKAOPAGE_HEADERS)
        except Exception as e:
            print(f"[WebtoonSearchMetadataProvider] 카카오페이지 검색 API 호출 실패: {e}")
            return []

        results = []
        for item in (data.get('result') or {}).get('list', []) or []:
            series_id = item.get('series_id')
            thumbnail = item.get('thumbnail')
            if not series_id or not thumbnail:
                continue

            category = ' / '.join(c for c in (item.get('category'), item.get('sub_category')) if c)
            results.append({
                'title': item.get('title', ''),
                'author': item.get('authors', ''),
                'publisher': f"카카오페이지 ({category})" if category else '카카오페이지',
                # on_issue='Y'는 연재중이 확실하지만 'N'이 완결을 보장하지는 않아서 완결 표시는 하지 않는다.
                'pubDate': '연재중' if item.get('on_issue') == 'Y' else '',
                'cover': f"{_KAKAOPAGE_IMAGE_URL}{thumbnail}",
                'description': '',
                'link': f"https://page.kakao.com/content/{series_id}",
            })
        return results

    def _search_kakaowebtoon(self, query, skip_titles):
        params = {'offset': 0, 'limit': _KAKAOWEBTOON_LIMIT, 'word': query}
        try:
            data = _fetch_json(f"{_KAKAOWEBTOON_SEARCH_API}?{urllib.parse.urlencode(params)}", _KAKAOWEBTOON_HEADERS)
        except Exception as e:
            print(f"[WebtoonSearchMetadataProvider] 카카오웹툰 검색 API 호출 실패: {e}")
            return []

        items = [
            item for item in (data.get('data') or {}).get('content', []) or []
            if item.get('id') and (item.get('title') or '').replace(' ', '') not in skip_titles
        ]
        if not items:
            return []

        with ThreadPoolExecutor(max_workers=5) as pool:
            details = list(pool.map(self._fetch_kakaowebtoon_detail, [item['id'] for item in items]))

        # 상세 조회가 실패해도 검색 결과 필드(세로 배경 이미지 등)로 최대한 채운다.
        results = [self._kakaowebtoon_result({**item, **detail}) for item, detail in zip(items, details)]
        return [r for r in results if r]

    def _fetch_kakaowebtoon_detail(self, content_id):
        try:
            return _fetch_json(f"{_KAKAOWEBTOON_DETAIL_API}{content_id}", _KAKAOWEBTOON_HEADERS).get('data') or {}
        except Exception as e:
            print(f"[WebtoonSearchMetadataProvider] 카카오웹툰 상세 API 호출 실패({content_id}): {e}")
            return {}

    def _kakaowebtoon_result(self, info):
        image = info.get('sharingThumbnailImage') or info.get('backgroundImage')
        if not info.get('id') or not image:
            return None

        authors = []
        for a in info.get('authors') or []:
            name = a.get('name')
            if name and a.get('type') != 'PUBLISHER' and name not in authors:
                authors.append(name)

        genre = info.get('genre')
        return {
            'title': info.get('title', ''),
            'author': ', '.join(authors),
            'publisher': f"카카오웹툰 ({genre})" if genre else '카카오웹툰',
            # 상세 API의 status는 완결작도 SELLING이라 연재 상태를 알 수 없다.
            'pubDate': '',
            'cover': f"{image}.webp",
            'description': info.get('synopsis') or info.get('catchphraseTwoLines', ''),
            'link': f"https://webtoon.kakao.com/content/{info.get('seoId', '')}/{info['id']}",
        }

    def _search_naver(self, query):
        try:
            data = _fetch_json(f"{_NAVER_SEARCH_API}?{urllib.parse.urlencode({'keyword': query})}", _HEADERS)
        except Exception as e:
            print(f"[WebtoonSearchMetadataProvider] 네이버웹툰 검색 API 호출 실패: {e}")
            return []

        results = []
        for bucket_key in ('searchWebtoonResult', 'searchBestChallengeResult', 'searchChallengeResult'):
            bucket = data.get(bucket_key) or {}
            for item in bucket.get('searchViewList', []) or []:
                title_id = item.get('titleId')
                if not title_id:
                    continue

                authors = ', '.join(
                    a.get('name', '') for a in (item.get('communityArtists') or []) if a.get('name')
                ) or item.get('displayAuthor', '')

                status = item.get('publishDescription') or ('완결' if item.get('finished') else '연재중')
                genres = ', '.join(
                    g.get('description', '') for g in (item.get('genreList') or []) if g.get('description')
                )

                results.append({
                    'title': item.get('titleName', ''),
                    'author': authors,
                    'publisher': f"네이버웹툰 ({genres})" if genres else '네이버웹툰',
                    'pubDate': status,
                    'cover': item.get('thumbnailUrl', ''),
                    'description': item.get('synopsis', ''),
                    'link': f"https://comic.naver.com/webtoon/list?titleId={title_id}",
                })
        return results

    def apply(self, db_type, book_id, item_data):
        gateway = self.get_db_gateway(db_type)

        book = gateway.fetch_one(
            "SELECT series_name, library_id FROM books WHERE id = ?", (book_id,)
        )
        if not book:
            return False, '대상 도서를 찾을 수 없습니다.'

        series_name = book['series_name']
        library_id = book['library_id']
        if not series_name:
            return False, '이 도서는 시리즈 정보가 없어 일괄 적용할 수 없습니다.'

        cover_url = item_data.get('cover')
        if not cover_url:
            return False, '선택한 검색 결과에 표지 이미지가 없습니다.'

        try:
            from services.cover_storage_service import get_covers_dir
            covers_dir = os.path.join(get_covers_dir(), str(library_id))
            os.makedirs(covers_dir, exist_ok=True)

            series_hash = hashlib.md5(f"{library_id}:{series_name}".encode('utf-8')).hexdigest()
            cover_filename = f"webtoon_{series_hash}.webp"
            dest_path = os.path.join(covers_dir, cover_filename)

            req = urllib.request.Request(cover_url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as response:
                img_data = response.read()
            try:
                with Image.open(io.BytesIO(img_data)) as img:
                    img.convert('RGB').save(dest_path, "WEBP", quality=85)
            except Exception as e:
                print(f"[WebtoonSearchMetadataProvider] WebP 인코딩 실패, 원본 바이너리 저장: {e}")
                with open(dest_path, 'wb') as f:
                    f.write(img_data)
        except Exception as e:
            return False, f'표지 이미지 다운로드 실패: {e}'

        stored_cover = f"{library_id}/{cover_filename}"

        try:
            rowcount = gateway.execute(
                """
                UPDATE books
                SET cover_image = ?, cover_updated_at = CURRENT_TIMESTAMP
                WHERE series_name = ? AND library_id = ? AND COALESCE(is_deleted, 0) = 0
                """,
                (stored_cover, series_name, library_id),
            )
        except Exception as e:
            return False, f'DB 일괄 업데이트 실패: {e}'

        try:
            from utils.cover_helper import invalidate_series_cover_cache
            invalidate_series_cover_cache(db_type=db_type, lib_id=library_id, series_name=series_name)
        except Exception:
            pass

        title = item_data.get('title', series_name)
        return True, f'"{title}" 표지를 시리즈 전체 {rowcount}권에 적용했습니다.'
