# -*- coding: utf-8 -*-
"""
author_other_books.py - 도서 상세 페이지 사이드바 "이 작가의 다른 도서" 위젯 샘플 플러그인

예전에는 코어(services/recommendation_service.py + /api/media/author-books)에
하드코딩되어 있던 기능을 detail_sidebar_widget 계약으로 분리한 참조 구현입니다.
같은 작가의 다른 시리즈를 코어 DB에서 직접 조회해 보여주며, 플러그인 개발자가
"관련도서"/"유사한 태그 도서"/그 외 완전히 다른 위젯(예: 음악 추천, 외부 링크)으로
교체하고 싶을 때 참고할 최소 예제입니다.
"""
import json
from plugins.metadata.base import BaseMetadataProvider

RECOMMEND_LIMIT = 20
INDEX_CACHE_TTL = 1800  # 30분 - 시리즈/작가 인덱스는 스캔 직후가 아니면 자주 바뀌지 않음


def _tokenize(raw):
    if not raw:
        return set()
    return {token.strip() for token in str(raw).split(',') if token.strip()}


class AuthorOtherBooksMetadataProvider(BaseMetadataProvider):
    """도서 상세 사이드바에 "이 작가의 다른 도서"를 표시하는 위젯 플러그인."""

    id = "author_other_books"
    name = "이 작가의 다른 도서"
    is_searchable = False
    config_schema = []
    detail_sidebar_widget = {
        "title": "이 작가의 다른 도서",
        "order": 50,
        "sessions": "all",
    }

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 메타데이터 적용을 지원하지 않습니다."

    @staticmethod
    def _resolve_cover_url(cover_image):
        """books.cover_image의 원본 저장값(파일명/상대경로)을 브라우저가 바로
        쓸 수 있는 /covers/... URL로 정규화한다. 이미 절대 URL이면 그대로 둔다."""
        if not cover_image:
            return None
        clean = str(cover_image).strip()
        if not clean:
            return None
        if clean.startswith("http://") or clean.startswith("https://") or clean.startswith("/"):
            return clean
        clean = clean.lstrip("/\\")
        if clean.lower().startswith("covers/"):
            clean = clean[len("covers/"):].lstrip("/\\")
        return f"/covers/{clean}" if clean else None

    def _get_series_author_index(self, db_type):
        """시리즈 단위 대표 정보(대표 book id, 커버, 포맷, 작가) 인덱스 조회.
        코어 services/recommendation_service.py의 인덱싱 로직과 동일한 그룹핑 규칙을
        플러그인 DB 게이트웨이(읽기 전용 쿼리)로 재구현한 것 - 플러그인은 코어 서비스
        내부 함수를 직접 import하지 않고 스스로 조회/가공한다.

        전체 books 테이블을 GROUP BY로 훑는 쿼리라 라이브러리가 크면 수 초가 걸릴 수 있다
        (실측: 상세 페이지를 열 때마다 매번 재실행되면서 위젯이 3초 이상 늦게 뜨는 원인이었음).
        도서 상세 페이지는 열릴 때마다 이 인덱스를 필요로 하지만 스캔 직후가 아니면 자주
        바뀌지 않으므로, 플러그인 전용 Redis 캐시(cache_get/cache_set)로 TTL 동안 재사용한다."""
        cache_key = f"series_author_index:{db_type}"
        cached = self.cache_get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        gateway = self.get_db_gateway(db_type)
        rows = gateway.fetch_all(
            """
            SELECT series_name, library_id,
                   MIN(id) AS id,
                   MAX(cover_image) AS cover_image,
                   MAX(file_format) AS file_format,
                   MAX(author) AS author
            FROM books
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND series_name IS NOT NULL AND series_name != ''
              AND author IS NOT NULL AND author != ''
            GROUP BY series_name, library_id
            """
        ) or []
        index_rows = [dict(row) for row in rows]

        try:
            self.cache_set(cache_key, json.dumps(index_rows, ensure_ascii=False), ttl=INDEX_CACHE_TTL)
        except Exception:
            pass

        return index_rows

    def get_detail_sidebar_data(self, db_type, context):
        series_name = (context or {}).get('series_name') or ''
        library_id = (context or {}).get('library_id')
        if not series_name:
            return {'success': False, 'error': 'series_name is required'}

        index_rows = self._get_series_author_index(db_type)

        target_row = next(
            (r for r in index_rows if r['series_name'] == series_name and (library_id is None or str(r['library_id']) == str(library_id))),
            None
        )
        if target_row is None:
            target_row = next((r for r in index_rows if r['series_name'] == series_name), None)

        target_tokens = _tokenize(target_row['author']) if target_row else set()
        if not target_tokens:
            # 작가 정보가 없으면 빈 목록 - 위젯 섹션은 프론트에서 자동으로 숨겨진다.
            return {'success': True, 'items': []}

        scored = []
        for row in index_rows:
            if row['series_name'] == series_name:
                continue
            overlap = len(target_tokens & _tokenize(row['author']))
            if overlap <= 0:
                continue
            scored.append((overlap, row))
        scored.sort(key=lambda t: t[0], reverse=True)

        items = []
        for _, row in scored[:RECOMMEND_LIMIT]:
            items.append({
                'book_id': row['id'],
                'series_name': row['series_name'],
                'library_id': row['library_id'],
                'cover': self._resolve_cover_url(row.get('cover_image')),
                'file_format': row.get('file_format'),
                'title': row['series_name'],
            })

        return {'success': True, 'items': items}
