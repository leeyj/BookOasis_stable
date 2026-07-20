# -*- coding: utf-8 -*-
import json
from repositories.metadata_repository import MetadataRepository

class MetadataService:
    @staticmethod
    def get_meta_recommend(db_type, series_name):
        rows = MetadataRepository.get_meta_recommend(db_type, series_name)
        return [
            {
                'id': r['id'],
                'series_name': r['series_name'],
                'author': r['author'] or '-',
                'publisher': r['publisher'] or '-',
                'summary': r['summary'],
                'cover_image': r['cover_image'] or ''
            }
            for r in rows
        ]

    @staticmethod
    def copy_metadata(db_type, target_series, target_lib_id, source_book_id):
        return MetadataRepository.copy_metadata(db_type, target_series, target_lib_id, source_book_id)

    @staticmethod
    def get_searchable_plugins():
        """수동 검색 모달에 사용 가능한 메타데이터 플러그인 목록 조회"""
        try:
            from services.metadata_factory import MetadataFactory
            all_providers = MetadataFactory.get_all_searchable_providers()
            return [p for p in all_providers if p.get('enabled', True)]
        except Exception as e:
            print(f"[MetadataService] Plugin list retrieval failed: {e}")
            return []

    @staticmethod
    def search_metadata(db_type, query, source=None):
        """지정된 source(플러그인 ID)를 이용해 메타데이터를 검색"""
        try:
            from services.metadata_factory import MetadataFactory
            provider = MetadataFactory.get_provider_by_id(source)
            return provider.search(db_type, query)
        except Exception as e:
            print(f"[MetadataService] Plugin search_metadata error (source: {source}): {e}")
            return []

    @staticmethod
    def apply_metadata(db_type, book_id, item_data, source=None):
        """지정된 source(플러그인 ID)를 이용해 선택한 메타데이터를 도서 정보에 적용"""
        try:
            from services.metadata_factory import MetadataFactory
            provider = MetadataFactory.get_provider_by_id(source)
            return provider.apply(db_type, book_id, item_data)
        except Exception as e:
            print(f"[MetadataService] Plugin apply_metadata error (source: {source}): {e}")
            return False, f"메타데이터 반영 실패: {str(e)}"

    @staticmethod
    def search_aladin(db_type, query):
        """하위 호환성 유지용"""
        from services.metadata_factory import MetadataFactory
        provider = MetadataFactory.get_provider_by_id('aladin')
        if provider:
            return provider.search(db_type, query)
        return []
