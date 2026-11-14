# -*- coding: utf-8 -*-
"""
db_writer.py – 스캐너 DB 업서트/배치 라이터 (SQLite / MariaDB 공용)

예전엔 db_writer_sqlite.py / db_writer_mariadb.py 두 벌이 placeholder(? / %s)와 upsert 절만 다른
같은 코드였다. 한 벌로 합치고 방언 차이는 _sql()과 _BOOKS_UPSERT에서만 다룬다.
SQL은 '?' placeholder로 쓰고, MariaDB면 실행 직전에 '%s'로 바꾼다
(이 파일의 SQL에는 문자열 리터럴 안의 '?'나 '%'가 없어 단순 치환으로 안전하다).
"""
import os
from collections import Counter

from database import is_mariadb_mode as _is_mariadb


def _sql(query):
    return query.replace('?', '%s') if _is_mariadb() else query


def _engine_label():
    return 'MariaDB' if _is_mariadb() else 'SQLite'


# bulk_insert_books의 file_path 충돌 시 갱신 절 (방언별)
_BOOKS_UPSERT = {
    'sqlite': """
        ON CONFLICT(file_path) DO UPDATE SET
            library_id   = EXCLUDED.library_id,
            is_deleted   = 0,
            title        = EXCLUDED.title,
            series_name  = EXCLUDED.series_name,
            cover_image  = CASE WHEN COALESCE(books.metadata_locked, 0) = 0 THEN COALESCE(NULLIF(EXCLUDED.cover_image, ''), books.cover_image) ELSE books.cover_image END,
            banner_image = CASE WHEN COALESCE(books.metadata_locked, 0) = 0 THEN COALESCE(NULLIF(EXCLUDED.banner_image, ''), books.banner_image) ELSE books.banner_image END,
            file_mtime   = EXCLUDED.file_mtime,
            file_size    = EXCLUDED.file_size
    """,
    'mariadb': """
        ON DUPLICATE KEY UPDATE
            library_id   = VALUES(library_id),
            is_deleted   = 0,
            title        = VALUES(title),
            series_name  = VALUES(series_name),
            cover_image  = CASE WHEN COALESCE(books.metadata_locked, 0) = 0 THEN COALESCE(NULLIF(VALUES(cover_image), ''), books.cover_image) ELSE books.cover_image END,
            banner_image = CASE WHEN COALESCE(books.metadata_locked, 0) = 0 THEN COALESCE(NULLIF(VALUES(banner_image), ''), books.banner_image) ELSE books.banner_image END,
            file_mtime   = VALUES(file_mtime),
            file_size    = VALUES(file_size)
    """,
}

_UPDATE_BOOK_METADATA_SQL = """
    UPDATE books SET
        series_name  = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE series_name END,
        cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), cover_image) ELSE cover_image END,
        cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
        banner_image = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), banner_image) ELSE banner_image END,
        banner_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE banner_updated_at END,
        author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), author) ELSE author END,
        isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), isbn) ELSE isbn END,
        publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), publisher) ELSE publisher END,
        link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), link) ELSE link END,
        score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != 0 THEN ? ELSE score END,
        summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), summary) ELSE summary END,
        release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), release_date) ELSE release_date END,
        genre        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), genre) ELSE genre END,
        tags         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), tags) ELSE tags END
    WHERE file_path = ?
"""

_BULK_UPDATE_BOOKS_SQL = """
    UPDATE books SET
        is_deleted   = 0,
        library_id   = CASE WHEN ? IS NOT NULL AND ? > 0 THEN ? ELSE library_id END,
        series_name  = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE series_name END,
        cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), cover_image) ELSE cover_image END,
        cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
        banner_image = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), banner_image) ELSE banner_image END,
        banner_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE banner_updated_at END,
        author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), author) ELSE author END,
        isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), isbn) ELSE isbn END,
        publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), publisher) ELSE publisher END,
        link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), link) ELSE link END,
        score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != 0 THEN ? ELSE score END,
        summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), summary) ELSE summary END,
        release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), release_date) ELSE release_date END,
        genre        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), genre) ELSE genre END,
        tags         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), tags) ELSE tags END,
        books_lv     = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), books_lv) ELSE books_lv END,
        publication_status = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), publication_status) ELSE publication_status END,
        cover_artist = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), cover_artist) ELSE cover_artist END,
        teams        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), teams) ELSE teams END,
        locations    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), locations) ELSE locations END,
        characters   = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), characters) ELSE characters END,
        file_mtime   = ?,
        file_size    = ?
    WHERE file_path = ?
"""

_INSERT_OFFSETS_SQL = """
    INSERT INTO book_offsets
    (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type, data_offset)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


def update_book_metadata(cursor, full_path, cover_image, merged_meta, series_name='', force=False, banner_image=None):
    """기존 도서 정보와 로컬 메타데이터를 병합 갱신한다.
    force는 호출부 호환용으로 남긴다 - 예전 두 분기(force/일반)의 SQL이 완전히 같았다."""
    cursor.execute(_sql(_UPDATE_BOOK_METADATA_SQL), (
        series_name, series_name, series_name,
        cover_image,
        cover_image, cover_image,
        banner_image or '',
        banner_image or '', banner_image or '',
        merged_meta['author'],
        merged_meta.get('isbn', ''),
        merged_meta['publisher'],
        merged_meta['link'],
        merged_meta['score'], merged_meta['score'],
        merged_meta['summary'],
        merged_meta['release_date'],
        merged_meta.get('genre', ''),
        merged_meta.get('tags', ''),
        full_path,
    ))


def insert_new_book_v2(cursor, library_id, full_path, filename, file_format, series_name, cover_image, merged_meta, file_mtime=0.0, file_size=0):
    """새 도서를 넣고 book_id를 돌려준다."""
    title, _ = os.path.splitext(filename)
    cursor.execute(_sql("""
        INSERT INTO books
        (library_id, title, series_name, author, isbn, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date, genre, tags, file_mtime, file_size)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """), (
        library_id,
        title,
        series_name,
        merged_meta['author'],
        merged_meta.get('isbn', ''),
        full_path,
        file_format,
        100 if file_format == 'epub' else 0,
        cover_image,
        merged_meta['publisher'],
        merged_meta['link'],
        merged_meta['score'],
        merged_meta['summary'],
        merged_meta['release_date'],
        merged_meta.get('genre', ''),
        merged_meta.get('tags', ''),
        file_mtime,
        file_size,
    ))
    return cursor.lastrowid


def save_book_offsets(cursor, book_id, filename, offsets_data):
    """오프셋 정보를 일괄 저장하고 books 요약(total_pages/has_offsets)을 갱신한다."""
    if not offsets_data:
        return

    cursor.execute(_sql("DELETE FROM book_offsets WHERE book_id = ?"), (book_id,))
    bulk_data = [(book_id, *offset) for offset in offsets_data]
    cursor.executemany(_sql(_INSERT_OFFSETS_SQL), bulk_data)
    cursor.execute(_sql("UPDATE books SET total_pages = ?, has_offsets = 1 WHERE id = ?"), (len(bulk_data), book_id))
    print(f"[Scanner-Offset-{_engine_label()}] '{filename}' offset DB index complete ({len(bulk_data)} pages)")


def bulk_update_books(cursor, update_data_list, force=False):
    """기존 도서 일괄 갱신. force는 호출부 호환용(예전 두 분기의 SQL이 같았다)."""
    if not update_data_list:
        return
    cursor.executemany(_sql(_BULK_UPDATE_BOOKS_SQL), [
        (row[0], row[0], row[0], row[1], row[1], row[1], *row[2:]) for row in update_data_list
    ])


def bulk_insert_books(cursor, insert_data_list):
    """새 도서 일괄 삽입. file_path가 겹치면 upsert."""
    if not insert_data_list:
        return
    query = """
        INSERT INTO books
        (library_id, title, series_name, author, isbn, file_path, file_format, total_pages, cover_image, banner_image, publisher, link, score, summary, release_date, genre, tags, books_lv, publication_status, cover_artist, teams, locations, characters, file_mtime, file_size, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """ + _BOOKS_UPSERT['mariadb' if _is_mariadb() else 'sqlite']
    cursor.executemany(_sql(query), insert_data_list)


def bulk_save_book_offsets(cursor, offsets_data_list):
    """여러 도서의 오프셋을 일괄 저장."""
    if not offsets_data_list:
        return

    book_ids = list(set([o[0] for o in offsets_data_list]))
    cursor.executemany(_sql("DELETE FROM book_offsets WHERE book_id = ?"), [(bid,) for bid in book_ids])
    cursor.executemany(_sql(_INSERT_OFFSETS_SQL), offsets_data_list)

    counts = Counter([o[0] for o in offsets_data_list])
    cursor.executemany(_sql("UPDATE books SET total_pages = ?, has_offsets = 1 WHERE id = ?"),
                       [(count, bid) for bid, count in counts.items()])
