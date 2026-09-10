# -*- coding: utf-8 -*-
"""
detail_view_demo.py - 도서 상세 페이지 본문 전체를 대체하는 detail_view 계약 참조 구현.

코어 상세 화면(표지/제목/시놉시스/볼륨 목록)을 그대로 흉내 내되 레이아웃만 다르게 짠
최소 예제입니다. 실제 데이터 조회 로직은 전혀 없으며 - 상세 화면이 이미 서버에서
{meta, books}로 넘겨준 데이터를 detail/script.js에서 그대로 렌더링만 합니다.
"""
from plugins.metadata.base import BaseMetadataProvider


class DetailViewDemoMetadataProvider(BaseMetadataProvider):
    """도서 상세 페이지 렌더러로 선택 가능한 데모 플러그인."""

    id = "detail_view_demo"
    name = "상세페이지 데모 화면"
    is_searchable = False
    config_schema = []
    detail_view = {
        "title": "데모 상세 화면 (가로 카드형)",
        "sessions": "all",
    }

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 메타데이터 적용을 지원하지 않습니다."
