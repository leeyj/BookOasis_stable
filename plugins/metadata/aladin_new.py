# -*- coding: utf-8 -*-
import os
import json
import urllib.request
import urllib.parse
from plugins.metadata.base import BaseMetadataProvider

class Aladin_newMetadataProvider(BaseMetadataProvider):
    """
    대시보드 메인 화면에 알라딘 오늘의 신간 목록을 제공하는 플러그인입니다.
    이 플러그인은 도서 검색 매칭이 아닌, 메인 화면 UI 전용입니다.
    """
    id = "aladin_new"
    name = "알라딘 오늘의 신간 데스크"
    is_searchable = True  # 플러그인 설정 화면에 표시하기 위해 True
    config_schema = [
        {"key": "ALADIN", "label": "알라딘 OpenAPI TTBKey", "type": "text", "required": True, "description": "대시보드에 알라딘 신간 도서를 불러오는 데 필요한 TTBKey입니다. 기존 키를 동일하게 입력해주세요."}
    ]

    def _get_ttbkey(self, db_type):
        import database
        ttbkey = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'PLUGIN_CONFIG_aladin_new'")
            row = cursor.fetchone()
            if row and row['value']:
                config = json.loads(row['value'])
                ttbkey = config.get('ALADIN')
            conn.close()
        except Exception:
            pass
        return ttbkey

    def search(self, db_type, query):
        """메인 화면 데스크 전용이므로 메타데이터 검색 모달에서는 빈 결과를 반환합니다."""
        return []

    def apply(self, db_type, book_id, item_data):
        """메인 화면 데스크 전용이므로 적용을 지원하지 않습니다."""
        return False, "이 플러그인은 대시보드 전용으로 메타데이터 매칭을 지원하지 않습니다."

    def get_new_releases(self, db_type, limit=10):
        print(f"[AladinNewMetadataProvider] get_new_releases 호출됨 (db_type: '{db_type}', limit: {limit})")
        ttbkey = self._get_ttbkey(db_type)
        if not ttbkey:
            return {'success': False, 'error': 'TTBKey가 설정되지 않았습니다. 환경설정 > 플러그인 설정에서 키를 등록해주세요.'}

        url = "http://www.aladin.co.kr/ttb/api/ItemList.aspx"
        params = {
            'ttbkey': ttbkey,
            'QueryType': 'ItemNewAll',
            'MaxResults': limit,
            'start': 1,
            'SearchTarget': 'Book',
            'output': 'js',
            'Version': '20131101',
            'Cover': 'Big'
        }
        
        try:
            query_string = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_string}"
            req = urllib.request.Request(
                full_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = response.read().decode('utf-8')
                if res_body.endswith(';'):
                    res_body = res_body[:-1]
                data = json.loads(res_body)
                
                if 'errorCode' in data:
                    return {'success': False, 'error': data.get('errorMessage')}
                    
                items = data.get('item', [])
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
                return {'success': True, 'books': results}
        except Exception as e:
            import traceback
            print(f"[AladinNewMetadataProvider] 신간 목록 호출 예외: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}
