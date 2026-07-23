# -*- coding: utf-8 -*-
"""
book_scan_repository.py – 도서(books) 및 오프셋(book_offsets) 백그라운드 스캔용 데이터 액세스 레이어
"""
import database

class BookScanRepository:
    @staticmethod
    def get_book_basic_info_raw(db_type, book_id):
        """도서 단일 행의 시리즈, 경로, 파일 포맷 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, library_id, title, series_name, file_path, file_format, cover_image
            FROM books WHERE id = ?
            """,
            (book_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_book_scanned_metadata(db_type, book_id, series_name, cover_image, meta):
        """스캐너 탐색 결과를 도서 메타데이터에 반영"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE books SET 
                    series_name  = COALESCE(NULLIF(?, ''), series_name),
                    cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? IS NOT NULL AND ? != '' THEN ? ELSE cover_image END,
                    cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                    author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), author) ELSE author END,
                    isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), isbn) ELSE isbn END,
                    publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), publisher) ELSE publisher END,
                    link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), link) ELSE link END,
                    score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != 0 THEN ? ELSE score END,
                    summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), summary) ELSE summary END,
                    release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), release_date) ELSE release_date END
                WHERE id = ?
                """,
                (
                    series_name,
                    cover_image, cover_image, cover_image,
                    cover_image, cover_image,
                    meta['author'],
                    meta.get('isbn', ''),
                    meta['publisher'],
                    meta['link'],
                    meta['score'], meta['score'],
                    meta['summary'],
                    meta['release_date'],
                    book_id
                )
            )

            # 도서의 library_id 및 최신 series_name 조회 후 series 테이블 커버 동기화
            cursor.execute("SELECT library_id, series_name FROM books WHERE id = ?", (book_id,))
            row = cursor.fetchone()
            if row and row['series_name'] and cover_image:
                lib_id = row['library_id']
                s_name = row['series_name']
                cursor.execute(
                    """
                    UPDATE series SET 
                        cover_image = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN ? ELSE cover_image END,
                        cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN CURRENT_TIMESTAMP ELSE cover_updated_at END
                    WHERE name = ? AND library_id = ?
                    """,
                    (cover_image, s_name, lib_id)
                )

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def sync_book_offsets_transaction(db_type, book_id, offsets_data):
        """특정 도서의 압축파일 오프셋 테이블 트랜잭션 동기화"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM book_offsets WHERE book_id = ?", (book_id,))
            bulk_data = [(book_id, *offset) for offset in offsets_data]
            cursor.executemany(
                """
                INSERT INTO book_offsets 
                (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                bulk_data
            )
            cursor.execute(
                """
                UPDATE books SET total_pages = ?, has_offsets = 1 WHERE id = ?
                """,
                (len(bulk_data), book_id)
            )
            conn.commit()
            return len(bulk_data)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
