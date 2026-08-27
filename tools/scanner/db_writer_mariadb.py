# -*- coding: utf-8 -*-
"""
db_writer_mariadb.py – MariaDB Native 스캐너 DB 업서트/배치 라이터
"""
import os

def update_book_metadata(cursor, full_path, cover_image, merged_meta, series_name='', force=False):
    """Execute merge update for existing book info and local metadata in MariaDB"""
    common_args = (
        cover_image,
        cover_image, cover_image,
        merged_meta['author'],
        merged_meta.get('isbn', ''),
        merged_meta['publisher'],
        merged_meta['link'],
        merged_meta['score'], merged_meta['score'],
        merged_meta['summary'],
        merged_meta['release_date'],
        merged_meta.get('genre', ''),
        merged_meta.get('tags', ''),
        full_path
    )
    if force:
        cursor.execute("""
            UPDATE books SET
                series_name  = CASE WHEN %s IS NOT NULL AND %s != '' THEN %s ELSE series_name END,
                cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), cover_image) ELSE cover_image END,
                cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND %s != '' AND %s IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), author) ELSE author END,
                isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), isbn) ELSE isbn END,
                publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), publisher) ELSE publisher END,
                link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), link) ELSE link END,
                score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND %s != 0 THEN %s ELSE score END,
                summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), summary) ELSE summary END,
                release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), release_date) ELSE release_date END,
                genre        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), genre) ELSE genre END,
                tags         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), tags) ELSE tags END
            WHERE file_path = %s
        """, (series_name, series_name, series_name) + common_args)
    else:
        cursor.execute("""
            UPDATE books SET
                series_name  = CASE WHEN %s IS NOT NULL AND %s != '' THEN %s ELSE series_name END,
                cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), cover_image) ELSE cover_image END,
                cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND %s != '' AND %s IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), author) ELSE author END,
                isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), isbn) ELSE isbn END,
                publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), publisher) ELSE publisher END,
                link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), link) ELSE link END,
                score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND %s != 0 THEN %s ELSE score END,
                summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), summary) ELSE summary END,
                release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), release_date) ELSE release_date END,
                genre        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), genre) ELSE genre END,
                tags         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), tags) ELSE tags END
            WHERE file_path = %s
        """, (series_name, series_name, series_name) + common_args)

def insert_new_book_v2(cursor, library_id, full_path, filename, file_format, series_name, cover_image, merged_meta, file_mtime=0.0, file_size=0):
    """Insert new book info to DB and return book_id in MariaDB"""
    title, _ = os.path.splitext(filename)
    cursor.execute("""
        INSERT INTO books 
        (library_id, title, series_name, author, isbn, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date, genre, tags, file_mtime, file_size) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
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
        file_size
    ))
    return cursor.lastrowid

def save_book_offsets(cursor, book_id, filename, offsets_data):
    """Bulk save offset info to DB and update books table summary in MariaDB"""
    if not offsets_data:
        return
        
    cursor.execute("DELETE FROM book_offsets WHERE book_id = %s", (book_id,))
    bulk_data = [(book_id, *offset) for offset in offsets_data]
    cursor.executemany("""
        INSERT INTO book_offsets
        (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type, data_offset)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, bulk_data)
    
    cursor.execute("""
        UPDATE books SET total_pages = %s, has_offsets = 1 WHERE id = %s
    """, (len(bulk_data), book_id))
    print(f"[Scanner-Offset-MariaDB] '{filename}' offset DB index complete ({len(bulk_data)} pages)")

def bulk_update_books(cursor, update_data_list, force=False):
    """Bulk update existing books in MariaDB"""
    if not update_data_list:
        return
    if force:
        cursor.executemany("""
            UPDATE books SET 
                is_deleted   = 0,
                library_id   = CASE WHEN %s IS NOT NULL AND %s > 0 THEN %s ELSE library_id END,
                series_name  = CASE WHEN %s IS NOT NULL AND %s != '' THEN %s ELSE series_name END,
                cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), cover_image) ELSE cover_image END,
                cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND %s != '' AND %s IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), author) ELSE author END,
                isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), isbn) ELSE isbn END,
                publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), publisher) ELSE publisher END,
                link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), link) ELSE link END,
                score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND %s != 0 THEN %s ELSE score END,
                summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), summary) ELSE summary END,
                release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), release_date) ELSE release_date END,
                genre        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), genre) ELSE genre END,
                tags         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), tags) ELSE tags END,
                file_mtime   = %s,
                file_size    = %s
            WHERE file_path = %s
        """, [
            (row[0], row[0], row[0], row[1], row[1], row[1], *row[2:]) for row in update_data_list
        ])
    else:
        cursor.executemany("""
            UPDATE books SET 
                is_deleted   = 0,
                library_id   = CASE WHEN %s IS NOT NULL AND %s > 0 THEN %s ELSE library_id END,
                series_name  = CASE WHEN %s IS NOT NULL AND %s != '' THEN %s ELSE series_name END,
                cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), cover_image) ELSE cover_image END,
                cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND %s != '' AND %s IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), author) ELSE author END,
                isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), isbn) ELSE isbn END,
                publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), publisher) ELSE publisher END,
                link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), link) ELSE link END,
                score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND %s != 0 THEN %s ELSE score END,
                summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), summary) ELSE summary END,
                release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), release_date) ELSE release_date END,
                genre        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), genre) ELSE genre END,
                tags         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(%s, ''), tags) ELSE tags END,
                file_mtime   = %s,
                file_size    = %s
            WHERE file_path = %s
        """, [
            (row[0], row[0], row[0], row[1], row[1], row[1], *row[2:]) for row in update_data_list
        ])

def bulk_insert_books(cursor, insert_data_list):
    """Bulk insert or upsert new books when file_path conflicts in Native MariaDB"""
    if not insert_data_list: return
    cursor.executemany("""
        INSERT INTO books 
        (library_id, title, series_name, author, isbn, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date, genre, tags, file_mtime, file_size, is_deleted) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
        ON DUPLICATE KEY UPDATE
            library_id   = VALUES(library_id),
            is_deleted   = 0,
            title        = VALUES(title),
            series_name  = VALUES(series_name),
            cover_image  = CASE WHEN COALESCE(books.metadata_locked, 0) = 0 THEN COALESCE(NULLIF(VALUES(cover_image), ''), books.cover_image) ELSE books.cover_image END,
            file_mtime   = VALUES(file_mtime),
            file_size    = VALUES(file_size)
    """, insert_data_list)

def bulk_save_book_offsets(cursor, offsets_data_list):
    """Bulk save book offsets in MariaDB"""
    if not offsets_data_list: return
    
    book_ids = list(set([o[0] for o in offsets_data_list]))
    cursor.executemany("DELETE FROM book_offsets WHERE book_id = %s", [(bid,) for bid in book_ids])
    
    cursor.executemany("""
        INSERT INTO book_offsets
        (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type, data_offset)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, offsets_data_list)
    
    from collections import Counter
    counts = Counter([o[0] for o in offsets_data_list])
    cursor.executemany("""
        UPDATE books SET total_pages = %s, has_offsets = 1 WHERE id = %s
    """, [(count, bid) for bid, count in counts.items()])
