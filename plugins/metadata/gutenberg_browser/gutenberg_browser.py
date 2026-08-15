# -*- coding: utf-8 -*-
"""
gutenberg_browser.py – Project Gutenberg(https://www.gutenberg.org) 브라우징 샘플 플러그인

이 플러그인은 코어 웹뷰/다운로드 API(window.BookOasisPlugin.openWebview /
.downloadToLibrary, plugins/metadata/plugin_README.md §10)를 실제로 시연하기 위한
샘플입니다. 검색/자동 메타데이터 매칭 기능은 제공하지 않으며, 카테고리 풀페이지
UI(index.html/style.css/script.js)만 사용합니다.

주의: gutenberg.org 자체는 앱이 기본 제공/추천하는 도메인이 아닙니다 — 이 플러그인을
사용하려면 사용자가 [설정 > 외부 도메인] 탭에서 직접 gutenberg.org를 화이트리스트에
등록해야 합니다.
"""
from plugins.metadata.base import BaseMetadataProvider


class GutenbergBrowserMetadataProvider(BaseMetadataProvider):
    id = "gutenberg_browser"
    name = "Project Gutenberg"
    is_searchable = False

    # 코어 좌측 내비게이션에 1등 시민 카테고리 메뉴로 노출
    category_tab = {
        "title": "Project Gutenberg",
        "icon": "fa-solid fa-book-atlas",
        "order": 95,
    }

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 검색/자동 매칭을 지원하지 않는 웹뷰 데모 플러그인입니다."
