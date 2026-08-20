# -*- coding: utf-8 -*-
"""
annotation_repository.py – MariaDB 전용 EPUB/TXT 뷰어 하이라이트(주석) CRUD 데이터 액세스 레이어.
"""
import database

class AnnotationRepository:
    @staticmethod
    def create_annotation(db_type, book_id, user_id, format, chapter_idx, start_offset,
                           end_offset, quote, prefix=None, suffix=None, color='#fbbf24', note=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO book_annotations
                    (book_id, user_id, format, chapter_idx, start_offset, end_offset, quote, prefix, suffix, color, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (book_id, user_id, format, chapter_idx, start_offset, end_offset, quote, prefix, suffix, color, note)
            )
            annotation_id = cursor.lastrowid
            conn.commit()
            return annotation_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_book_annotations(db_type, book_id, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT * FROM book_annotations
                WHERE book_id = %s AND user_id = %s
                ORDER BY chapter_idx ASC, start_offset ASC
                """,
                (book_id, user_id)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows] if rows else []
        finally:
            conn.close()

    @staticmethod
    def get_annotation_by_id(db_type, annotation_id, user_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if user_id is not None:
                cursor.execute("SELECT * FROM book_annotations WHERE id = %s AND user_id = %s", (annotation_id, user_id))
            else:
                cursor.execute("SELECT * FROM book_annotations WHERE id = %s", (annotation_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def update_annotation(db_type, annotation_id, user_id, color, note):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE book_annotations
                SET color = %s, note = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                """,
                (color, note, annotation_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_plugin_marker(db_type, annotation_id, user_id, marker):
        """플러그인 컨텍스트 메뉴 액션 응답의 'marker' 필드로 하이라이트에 작은 표시(예: '*')를
        붙이거나 뗀다. 실제 메모/주석 내용은 코어가 모르며(플러그인이 자체 저장소에 보관),
        이 컬럼은 순수하게 "이 하이라이트에 플러그인이 뭔가 남겨뒀다"는 시각적 신호일 뿐이다.
        여러 플러그인이 같은 하이라이트에 마커를 설정하면 마지막에 설정한 값으로 덮어써진다."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE book_annotations SET plugin_marker = %s WHERE id = %s AND user_id = %s",
                (marker or None, annotation_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def delete_annotation(db_type, annotation_id, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM book_annotations WHERE id = %s AND user_id = %s", (annotation_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
