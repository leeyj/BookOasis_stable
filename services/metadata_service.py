# -*- coding: utf-8 -*-
import json
import database

class MetadataService:
    @staticmethod
    def get_meta_recommend(db_type, series_name):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MIN(id) AS id, series_name, author, publisher, summary, MAX(cover_image) AS cover_image
            FROM books
            WHERE series_name LIKE ? AND (summary IS NOT NULL AND summary != '' AND summary != '등록된 설명이 없습니다.')
            GROUP BY series_name
            LIMIT 3
        """, (f"%{series_name}%",))
        rows = cursor.fetchall()
        conn.close()
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
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        # 커버 이미지는 제외하고 순수 텍스트 메타 정보만 가져옴
        cursor.execute("""
            SELECT author, publisher, summary, link, score
            FROM books WHERE id = ?
        """, (source_book_id,))
        source = cursor.fetchone()
        
        if not source:
            conn.close()
            return False, '원본 메타데이터를 찾을 수 없습니다.'
            
        # 커버 이미지(cover_image)는 건드리지 않고 텍스트 메타 정보만 업데이트
        cursor.execute("""
            UPDATE books
            SET author = ?, publisher = ?, summary = ?, link = ?, score = ?
            WHERE series_name = ? AND library_id = ?
        """, (
            source['author'],
            source['publisher'],
            source['summary'],
            source['link'],
            source['score'],
            target_series,
            target_lib_id
        ))
        conn.commit()
        conn.close()
        return True, f'"{target_series}"에 추천 메타데이터가 정상 복사 및 적재되었습니다.'

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
        return MetadataService.search_metadata(db_type, query, 'aladin')

    @staticmethod
    def apply_aladin_metadata(db_type, book_id, aladin_item):
        """하위 호환성 유지용"""
        return MetadataService.apply_metadata(db_type, book_id, aladin_item, 'aladin')
