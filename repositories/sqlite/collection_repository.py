# -*- coding: utf-8 -*-
import database

class CollectionRepository:
    @staticmethod
    def create_collection(db_type, user_id, name, description=None, color='#7c3aed', cover_image=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO collections (user_id, name, description, color, cover_image)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, name, description, color, cover_image)
            )
            coll_id = cursor.lastrowid
            conn.commit()
            return coll_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_user_collections(db_type, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT c.*, COUNT(ci.id) AS item_count
                FROM collections c
                LEFT JOIN collection_items ci ON ci.collection_id = c.id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.created_at DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows] if rows else []
        finally:
            conn.close()

    @staticmethod
    def get_collection_by_id(db_type, collection_id, user_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if user_id:
                cursor.execute("SELECT * FROM collections WHERE id = ? AND user_id = ?", (collection_id, user_id))
            else:
                cursor.execute("SELECT * FROM collections WHERE id = ?", (collection_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def update_collection(db_type, collection_id, user_id, name, description=None, color='#7c3aed', cover_image=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE collections
                SET name = ?, description = ?, color = ?, cover_image = ?
                WHERE id = ? AND user_id = ?
                """,
                (name, description, color, cover_image, collection_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def delete_collection(db_type, collection_id, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM collection_items WHERE collection_id = ?", (collection_id,))
            cursor.execute("DELETE FROM collections WHERE id = ? AND user_id = ?", (collection_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def add_item_to_collection(db_type, collection_id, book_id=None, series_name=None, audiobook_id=None, video_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            # Check existing to prevent duplicate constraint exception
            if book_id is not None:
                cursor.execute("SELECT id FROM collection_items WHERE collection_id = ? AND book_id = ?", (collection_id, book_id))
            elif series_name is not None:
                cursor.execute("SELECT id FROM collection_items WHERE collection_id = ? AND series_name = ?", (collection_id, series_name))
            elif audiobook_id is not None:
                cursor.execute("SELECT id FROM collection_items WHERE collection_id = ? AND audiobook_id = ?", (collection_id, audiobook_id))
            elif video_id is not None:
                cursor.execute("SELECT id FROM collection_items WHERE collection_id = ? AND video_id = ?", (collection_id, video_id))
            else:
                return None

            if cursor.fetchone():
                return None  # Already exists

            cursor.execute(
                """
                INSERT INTO collection_items (collection_id, book_id, series_name, audiobook_id, video_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (collection_id, book_id, series_name, audiobook_id, video_id)
            )
            item_id = cursor.lastrowid
            conn.commit()
            return item_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def remove_item_from_collection(db_type, collection_id, item_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM collection_items WHERE collection_id = ? AND id = ?", (collection_id, item_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_collection_items(db_type, collection_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT ci.*,
                       b.title AS book_title, b.cover_image AS book_cover, b.series_name AS book_series, b.file_format AS book_format,
                       ab.title AS audiobook_title, ab.folder_name AS audiobook_folder,
                       v.title AS video_title, v.folder_name AS video_folder
                FROM collection_items ci
                LEFT JOIN books b ON b.id = ci.book_id
                LEFT JOIN audiobooks ab ON ab.id = ci.audiobook_id
                LEFT JOIN videos v ON v.id = ci.video_id
                WHERE ci.collection_id = ?
                ORDER BY ci.sort_order ASC, ci.created_at ASC
                """,
                (collection_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows] if rows else []
        finally:
            conn.close()
