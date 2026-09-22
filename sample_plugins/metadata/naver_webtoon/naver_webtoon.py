# -*- coding: utf-8 -*-
import hashlib
import io
import json
import os
import urllib.parse
import urllib.request

from PIL import Image

from plugins.metadata.base import BaseMetadataProvider

_SEARCH_API = "https://comic.naver.com/api/search/all"
_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


class NaverWebtoonMetadataProvider(BaseMetadataProvider):
    """네이버웹툰 공식 검색 API(로그인/키 불필요)로 시리즈를 찾아 표지를 적용합니다.

    웹툰/컷툰은 권별 표지가 따로 의미가 없는데도 스캐너가 각 회차 CBZ의 첫 페이지를
    표지로 자동 추출해버려서, 시리즈 대표 이미지를 매 권 수동으로 올려야 하는 반복
    작업이 생긴다. apply()는 기존 단건 검색/적용 UI를 그대로 쓰되, 선택된 표지를
    해당 book_id 하나가 아니라 같은 series_name의 모든 권에 한 번에 반영한다.
    """

    id = "naver_webtoon"
    name = "네이버웹툰 시리즈 표지"
    is_searchable = True
    config_schema = []

    def search(self, db_type, query):
        query = (query or '').strip()
        if not query:
            return []

        url = f"{_SEARCH_API}?{urllib.parse.urlencode({'keyword': query})}"
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"[NaverWebtoonMetadataProvider] 검색 API 호출 실패: {e}")
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
            cover_filename = f"naverwebtoon_{series_hash}.webp"
            dest_path = os.path.join(covers_dir, cover_filename)

            req = urllib.request.Request(cover_url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as response:
                img_data = response.read()
            try:
                with Image.open(io.BytesIO(img_data)) as img:
                    img.convert('RGB').save(dest_path, "WEBP", quality=85)
            except Exception as e:
                print(f"[NaverWebtoonMetadataProvider] WebP 인코딩 실패, 원본 바이너리 저장: {e}")
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
