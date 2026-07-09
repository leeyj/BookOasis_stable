# -*- coding: utf-8 -*-
import json
import urllib.request
import urllib.parse
from plugins.metadata.base import BaseMetadataProvider


class AladinNewMetadataProvider(BaseMetadataProvider):
    """
    대시보드 메인 화면에 알라딘 오늘의 신간 목록을 제공하는 플러그인입니다.
    이 플러그인은 도서 검색 매칭이 아닌, 메인 화면 UI 전용입니다.
    """
    id = "aladin_new"
    name = "알라딘 오늘의 신간 데스크"
    is_searchable = True  # 플러그인 설정 화면에 표시하기 위해 True
    dashboard_widget = {
        'title': '알라딘 오늘의 신간',
        'subtitle': '알라딘 신간 도서 정보를 대시보드에 표시합니다.',
        'provider': 'Aladin',
        'icon': 'fa-solid fa-book-open',
        'limit': 10,
    }
    config_schema = [
        {
            "key": "ALADIN",
            "label": "알라딘 OpenAPI TTBKey",
            "type": "text",
            "required": True,
            "description": "대시보드에 알라딘 신간 도서를 불러오는 데 필요한 TTBKey입니다. 기존 키를 동일하게 입력해주세요."
        }
    ]

    def _get_ttbkey(self, db_type):
        ttbkey = None
        try:
            config = self.get_plugin_config(db_type, default={})
            if isinstance(config, dict):
                ttbkey = config.get('ALADIN')
        except Exception:
            pass
        return ttbkey

    def search(self, db_type, query):
        """메인 화면 데스크 전용이므로 메타데이터 검색 모달에서는 빈 결과를 반환합니다."""
        return []

    def apply(self, db_type, book_id, item_data):
        """메인 화면 데스크 전용이므로 적용을 지원하지 않습니다."""
        return False, "이 플러그인은 대시보드 전용으로 메타데이터 매칭을 지원하지 않습니다."

    def _fetch_new_releases(self, db_type, limit=10):
        print(f"[AladinNewMetadataProvider] _fetch_new_releases 호출됨 (db_type: '{db_type}', limit: {limit})")
        ttbkey = self._get_ttbkey(db_type)
        if not ttbkey:
            return {
                'success': False,
                'error': 'TTBKey가 설정되지 않았습니다. 환경설정 > 플러그인 설정에서 키를 등록해주세요.'
            }

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

    def get_dashboard_data(self, db_type, limit=10):
        """대시보드 동적 위젯 공통 규격으로 데이터를 반환합니다."""
        result = self._fetch_new_releases(db_type, limit=limit)
        if not result.get('success'):
            return result
        return {
            'success': True,
            'items': result.get('books', [])
        }

    def get_context_menu_items(self, db_type, context):
        """도서 컨텍스트 메뉴에 플러그인 항목을 추가합니다."""
        return [
            {
                'id': 'open_aladin_search',
                'label': '알라딘에서 제목 검색',
                'icon': 'fa-solid fa-up-right-from-square',
            }
        ]

    def run_context_menu_action(self, db_type, action_id, context):
        """도서 컨텍스트 메뉴 액션 실행."""
        if action_id != 'open_aladin_search':
            return {'success': False, 'error': f'지원하지 않는 액션입니다: {action_id}'}

        title = (context or {}).get('book_title') or ''
        if not title:
            return {'success': False, 'error': '도서 제목 정보가 없어 알라딘 검색을 실행할 수 없습니다.'}

        query = urllib.parse.urlencode({'SearchTarget': 'All', 'SearchWord': title})
        url = f"https://www.aladin.co.kr/search/wsearchresult.aspx?{query}"

        return {
            'success': True,
            'message': '알라딘 검색 페이지를 새 탭으로 엽니다.',
            'open_url': url,
        }
