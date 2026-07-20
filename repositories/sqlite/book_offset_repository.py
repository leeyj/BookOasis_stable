# -*- coding: utf-8 -*-
"""
book_offset_repository.py – ZIP 파일 압축 해제 고속화 오프셋 정보(book_offsets) 전담 데이터 액세스 레이어
"""
import database

class BookOffsetRepository:
    @staticmethod
    def get_book_offset(db_type, book_id, page_idx):
        """특정 도서 및 페이지 인덱스에 해당하는 ZIP 압축 파일 헤더 오프셋 데이터 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT filename, local_header_offset, compress_size, file_size, compress_type
            FROM book_offsets
            WHERE book_id = ? AND page_idx = ?
            """,
            (book_id, page_idx),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
