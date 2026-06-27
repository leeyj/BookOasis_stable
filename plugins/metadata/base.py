# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

class BaseMetadataProvider(ABC):
    """
    모든 도서 메타데이터 제공 플러그인이 구현해야 하는 표준 인터페이스입니다.
    """
    id = "base"
    name = "기본 제공자"
    is_searchable = True
    config_schema = []
    enabled = True

    @abstractmethod
    def search(self, db_type, query):
        """
        주어진 검색어(query)로 도서 후보군 목록을 검색합니다.
        
        Args:
            db_type (str): 데이터베이스 타입 ('prod' 또는 'dev')
            query (str): 검색어 (도서 제목 등)
            
        Returns:
            list[dict]: 검색 결과 목록. 각 dict는 다음 필드를 포함해야 합니다.
                - 'title' (str): 도서 제목
                - 'author' (str): 저자명
                - 'publisher' (str): 출판사명
                - 'pubDate' (str): 출간일
                - 'cover' (str): 표지 이미지 URL
                - 'description' (str): 책 소개/설명
                - 'link' (str): 상세 정보 페이지 URL
        """
        pass

    @abstractmethod
    def apply(self, db_type, book_id, item_data):
        """
        선택된 메타데이터 항목(item_data)을 특정 도서(book_id)에 적용합니다.
        필요 시 표지 이미지를 다운로드하여 저장하고 DB 레코드를 업데이트합니다.
        
        Args:
            db_type (str): 데이터베이스 타입 ('prod' 또는 'dev')
            book_id (int): 변경할 도서의 ID
            item_data (dict): 적용할 도서 메타데이터 정보 (search 결과 중 하나의 아이템)
            
        Returns:
            tuple[bool, str]: (성공 여부, 메시지)
        """
        pass
