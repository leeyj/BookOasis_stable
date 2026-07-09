# -*- coding: utf-8 -*-
import urllib.parse

from plugins.metadata.base import BaseMetadataProvider


class NaverBookMetadataProvider(BaseMetadataProvider):
    """Open Naver Book search from the book context menu."""

    id = "naver_book"
    name = "네이버 도서 검색"
    is_searchable = False
    config_schema = []

    def search(self, db_type, query):
        print(f"[NaverBookMetadataProvider] search called db_type={db_type!r} query={query!r}")
        return []

    def apply(self, db_type, book_id, item_data):
        print(f"[NaverBookMetadataProvider] apply called db_type={db_type!r} book_id={book_id!r}")
        return False, "네이버 도서 검색 플러그인은 메타데이터 적용을 지원하지 않습니다."

    def get_context_menu_items(self, db_type, context):
        print(f"[NaverBookMetadataProvider] get_context_menu_items db_type={db_type!r} context={context!r}")
        return [
            {
                "id": "open_naver_book_search",
                "label": "네이버 도서에서 검색",
                "icon": "fa-solid fa-book-open",
            }
        ]

    def _build_search_query(self, db_type, context):
        book_id = (context or {}).get("book_id")
        title = (context or {}).get("book_title") or ""
        author = ""

        print(f"[NaverBookMetadataProvider] building query book_id={book_id!r} title={title!r} author={author!r}")

        if book_id:
            try:
                gateway = self.get_db_gateway(db_type)
                row = gateway.fetch_one("SELECT title, author FROM books WHERE id = ?", (book_id,))
                if row:
                    title = row["title"] or title
                    author = row["author"] or ""
                    print(f"[NaverBookMetadataProvider] db row found title={title!r} author={author!r}")
                else:
                    print(f"[NaverBookMetadataProvider] db row missing for book_id={book_id!r}")
            except Exception:
                import traceback
                print(f"[NaverBookMetadataProvider] db lookup failed: {traceback.format_exc()}")

        query_parts = [part.strip() for part in [title, author] if part and str(part).strip()]
        query = " ".join(query_parts).strip()
        print(f"[NaverBookMetadataProvider] built query={query!r}")
        return query

    def run_context_menu_action(self, db_type, action_id, context):
        print(f"[NaverBookMetadataProvider] run_context_menu_action db_type={db_type!r} action_id={action_id!r} context={context!r}")
        if action_id != "open_naver_book_search":
            return {"success": False, "error": f"지원하지 않는 액션입니다: {action_id}"}

        query = self._build_search_query(db_type, context)
        if not query:
            print("[NaverBookMetadataProvider] empty query, aborting")
            return {"success": False, "error": "검색할 도서 제목 정보가 없습니다."}

        url = "https://search.shopping.naver.com/book/search?" + urllib.parse.urlencode({
            "bookTabType": "ALL",
            "pageIndex": 1,
            "pageSize": 40,
            "query": query,
            "sort": "REL",
        })
        print(f"[NaverBookMetadataProvider] open_url={url!r}")
        return {
            "success": True,
            "message": "네이버 도서 검색 페이지를 새 탭으로 엽니다.",
            "open_url": url,
        }
