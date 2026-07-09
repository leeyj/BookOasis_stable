# -*- coding: utf-8 -*-
import os
import json
import urllib.request
import urllib.parse
import hashlib
from PIL import Image
import io
from plugins.metadata.base import BaseMetadataProvider


class AladinMetadataProvider(BaseMetadataProvider):
    """
    한국 알라딘 OpenAPI를 이용해 도서 정보를 검색하고 적용하는 플러그인입니다.
    """
    id = "aladin"
    name = "알라딘 도서 검색"
    is_searchable = True
    config_schema = [
        {
            "key": "ALADIN",
            "label": "알라딘 OpenAPI TTBKey",
            "type": "text",
            "required": True,
            "description": "국내 도서 정보 메타데이터 및 책 표지를 자동으로 수집하는 데 필요한 알라딘 API 키입니다."
        }
    ]

    def _get_ttbkey(self, db_type):
        ttbkey = None
        print(f"[AladinMetadataProvider] TTBKey DB 조회 시작 (db_type: {db_type})")
        try:
            config = self.get_plugin_config(db_type, default={})
            if isinstance(config, dict):
                ttbkey = config.get('ALADIN')
                if ttbkey:
                    masked = ttbkey[:4] + "****" if len(ttbkey) > 4 else ttbkey
                    print(f"[AladinMetadataProvider] 1단계: 플러그인 전용 설정에서 TTBKey 획득 성공 ({masked})")
        except Exception as e:
            print(f"[AladinMetadataProvider] TTBKey DB 조회 중 예외 발생: {e}")

        if not ttbkey:
            print("[AladinMetadataProvider] [경고] 모든 경로에서 TTBKey를 획득하는 데 실패했습니다.")
        return ttbkey

    def search(self, db_type, query):
        print(f"[AladinMetadataProvider] search 호출됨 (query: '{query}', db_type: '{db_type}')")
        if not query:
            print("[AladinMetadataProvider] 검색어가 비어 있어 검색을 건너뜁니다.")
            return []

        ttbkey = self._get_ttbkey(db_type)
        if not ttbkey:
            print("[AladinMetadataProvider] TTBKey가 설정되어 있지 않아 OpenAPI 요청을 중단합니다.")
            return []

        url = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx"
        params = {
            'ttbkey': ttbkey,
            'Query': query,
            'QueryType': 'Title',
            'MaxResults': 50,
            'start': 1,
            'SearchTarget': 'Book',
            'output': 'js',
            'Version': '20131101'
        }

        try:
            query_string = urllib.parse.urlencode(params)
            masked_ttbkey = ttbkey[:4] + "****" if len(ttbkey) > 4 else ttbkey
            masked_query_string = query_string.replace(ttbkey, masked_ttbkey)
            print(f"[AladinMetadataProvider] API 요청 전송: {url}?{masked_query_string}")

            full_url = f"{url}?{query_string}"
            req = urllib.request.Request(
                full_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                print(f"[AladinMetadataProvider] API 응답 수신 성공 (Status: {response.status})")
                res_body = response.read().decode('utf-8')
                print(f"[AladinMetadataProvider] API 응답 원문 바디: {res_body}")

                if res_body.endswith(';'):
                    res_body = res_body[:-1]
                data = json.loads(res_body)

                if 'errorCode' in data:
                    print(f"[AladinMetadataProvider] 알라딘 API 에러 반환: [{data.get('errorCode')}] {data.get('errorMessage')}")
                    return []

                items = data.get('item', [])
                print(f"[AladinMetadataProvider] 파싱 성공, 검색된 도서 개수: {len(items)}")

                results = []
                for item in items:
                    results.append({
                        'title': item.get('title'),
                        'author': item.get('author'),
                        'publisher': item.get('publisher'),
                        'pubDate': item.get('pubDate'),
                        'cover': item.get('cover'),
                        'description': item.get('description', ''),
                        'link': item.get('link')
                    })
                return results
        except Exception as e:
            import traceback
            print(f"[AladinMetadataProvider] 알라딘 API 호출 에러 예외 발생: {e}")
            print(f"[AladinMetadataProvider] 예외 트레이스백: {traceback.format_exc()}")
            return []

    def apply(self, db_type, book_id, item_data):
        gateway = self.get_db_gateway(db_type)

        try:
            book = gateway.fetch_one("SELECT file_path, series_name, library_id FROM books WHERE id = ?", (book_id,))
            if not book:
                return False, '대상 도서를 찾을 수 없습니다.'

            file_path = book['file_path']
            library_id = book['library_id']

            cover_url = item_data.get('cover')
            cover_filename = None

            if cover_url:
                try:
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
                    covers_dir = os.path.join(base_dir, 'covers', str(library_id))
                    os.makedirs(covers_dir, exist_ok=True)

                    filename = os.path.basename(file_path)
                    book_hash = hashlib.md5(filename.encode('utf-8')).hexdigest()
                    cover_filename = f"book_{book_hash}.webp"
                    dest_path = os.path.join(covers_dir, cover_filename)

                    req = urllib.request.Request(
                        cover_url,
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                    )
                    with urllib.request.urlopen(req, timeout=10) as response:
                        img_data = response.read()
                        try:
                            with Image.open(io.BytesIO(img_data)) as img:
                                img.save(dest_path, "WEBP", quality=80)
                        except Exception as e:
                            print(f"[AladinMetadataProvider] WebP 인코딩 실패, 원본 바이너리 저장: {e}")
                            with open(dest_path, 'wb') as img_f:
                                img_f.write(img_data)
                    print(f"[AladinMetadataProvider] 알라딘 커버 이미지 다운로드 완료: {cover_url} -> {dest_path}")

                    cover_filename = f"{library_id}/{cover_filename}"
                except Exception as e:
                    print(f"[AladinMetadataProvider] 커버 다운로드 실패: {e}")
                    cover_filename = None

            try:
                from tools.scanner import clean_html_tags
                description = clean_html_tags(item_data.get('description', ''))
            except Exception:
                description = item_data.get('description', '')

            title = item_data.get('title', '')
            author = item_data.get('author', '')
            publisher = item_data.get('publisher', '')
            link = item_data.get('link', '')

            gateway.execute("""
                UPDATE books
                SET author = ?,
                    publisher = ?,
                    summary = ?,
                    link = ?,
                    cover_image = COALESCE(NULLIF(?, ''), cover_image),
                    cover_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                author,
                publisher,
                description,
                link,
                cover_filename,
                book_id
            ))

            return True, f'"{title}" 메타데이터가 도서 정보에 성공적으로 반영되었습니다.'
        except Exception as e:
            return False, f'DB 업데이트 오류: {str(e)}'
