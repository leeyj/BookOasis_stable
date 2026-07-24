# -*- coding: utf-8 -*-
import os

def update_book_metadata(cursor, full_path, cover_image, merged_meta, series_name='', force=False):
    """Execute merge update for existing book info and local metadata"""
    # force=True: 경로에서 파싱한 series_name으로 강제 갱신
    # force=False: 일반 스캔에서도 파싱된 series_name이 있으면 적극 반영
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
                series_name  = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE series_name END,
                cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), cover_image) ELSE cover_image END,
                cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
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
        """, (series_name, series_name, series_name) + common_args)
    else:
        cursor.execute("""
            UPDATE books SET
                series_name  = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE series_name END,
                cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), cover_image) ELSE cover_image END,
                cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
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
        """, (series_name, series_name, series_name) + common_args)


def insert_new_book(cursor, library_id, filename, series_name, cover_image, merged_meta):
    """Insert new book info to DB and return book_id"""
    title, _ = os.path.splitext(filename)
    file_format = os.path.splitext(filename)[1].replace('.', '').lower()
    full_path = os.path.join(os.path.dirname(cover_image) if cover_image and '/' in cover_image else '', filename) # Actual path overridden or passed from outside.
    
    # Caution: Safer to pass full_path exactly from outside as function argument.
    # Enhance function definition as follows.
    pass

def insert_new_book_v2(cursor, library_id, full_path, filename, file_format, series_name, cover_image, merged_meta, file_mtime=0.0, file_size=0):
    """Insert new book info to DB and return book_id"""
    title, _ = os.path.splitext(filename)
    cursor.execute("""
        INSERT INTO books 
        (library_id, title, series_name, author, isbn, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date, genre, tags, file_mtime, file_size) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    """Bulk save offset info to DB and update books table summary"""
    if not offsets_data:
        return
        
    cursor.execute("DELETE FROM book_offsets WHERE book_id = ?", (book_id,))
    bulk_data = [(book_id, *offset) for offset in offsets_data]
    cursor.executemany("""
        INSERT INTO book_offsets 
        (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, bulk_data)
    
    cursor.execute("""
        UPDATE books SET total_pages = ?, has_offsets = 1 WHERE id = ?
    """, (len(bulk_data), book_id))
    print(f"[Scanner-Offset] '{filename}' offset DB index complete ({len(bulk_data)} pages)")

def bulk_update_books(cursor, update_data_list, force=False):
    """Bulk update existing books
    
    update_data_list 각 항목 형식:
            force=False: (series_name, cover_image, cover_image, cover_image, author, publisher, link, score, score, summary, release_date, genre, tags, file_mtime, file_size, file_path)
            force=True : series_name 강제 반영
    """
    if not update_data_list:
        return
    if force:
        cursor.executemany("""
            UPDATE books SET 
                is_deleted   = 0,
                library_id   = CASE WHEN ? IS NOT NULL AND ? > 0 THEN ? ELSE library_id END,
                series_name  = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE series_name END,
                cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), cover_image) ELSE cover_image END,
                cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), author) ELSE author END,
                isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), isbn) ELSE isbn END,
                publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), publisher) ELSE publisher END,
                link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), link) ELSE link END,
                score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != 0 THEN ? ELSE score END,
                summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), summary) ELSE summary END,
                release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), release_date) ELSE release_date END,
                genre        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), genre) ELSE genre END,
                tags         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), tags) ELSE tags END,
                file_mtime   = ?,
                file_size    = ?
            WHERE file_path = ?
        """, [
            # library_id 3회 + series_name 3회
            (row[0], row[0], row[0], row[1], row[1], row[1], *row[2:]) for row in update_data_list
        ])
    else:
        cursor.executemany("""
            UPDATE books SET 
                is_deleted   = 0,
                library_id   = CASE WHEN ? IS NOT NULL AND ? > 0 THEN ? ELSE library_id END,
                series_name  = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE series_name END,
                cover_image  = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), cover_image) ELSE cover_image END,
                cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
                author       = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), author) ELSE author END,
                isbn         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), isbn) ELSE isbn END,
                publisher    = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), publisher) ELSE publisher END,
                link         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), link) ELSE link END,
                score        = CASE WHEN COALESCE(metadata_locked, 0) = 0 AND ? != 0 THEN ? ELSE score END,
                summary      = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), summary) ELSE summary END,
                release_date = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), release_date) ELSE release_date END,
                genre        = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), genre) ELSE genre END,
                tags         = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN COALESCE(NULLIF(?, ''), tags) ELSE tags END,
                file_mtime   = ?,
                file_size    = ?
            WHERE file_path = ?
        """, [
            (row[0], row[0], row[0], row[1], row[1], row[1], *row[2:]) for row in update_data_list
        ])

def bulk_insert_books(cursor, insert_data_list):
    """Bulk insert or upsert new books when file_path conflicts"""
    if not insert_data_list: return
    cursor.executemany("""
        INSERT INTO books 
        (library_id, title, series_name, author, isbn, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date, genre, tags, file_mtime, file_size, is_deleted) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(file_path) DO UPDATE SET
            library_id   = EXCLUDED.library_id,
            is_deleted   = 0,
            title        = EXCLUDED.title,
            series_name  = EXCLUDED.series_name,
            cover_image  = CASE WHEN COALESCE(books.metadata_locked, 0) = 0 THEN COALESCE(NULLIF(EXCLUDED.cover_image, ''), books.cover_image) ELSE books.cover_image END,
            file_mtime   = EXCLUDED.file_mtime,
            file_size    = EXCLUDED.file_size
    """, insert_data_list)

def bulk_save_book_offsets(cursor, offsets_data_list):
    """Bulk save book offsets"""
    if not offsets_data_list: return
    
    # First delete existing offsets for these books
    book_ids = list(set([o[0] for o in offsets_data_list]))
    cursor.executemany("DELETE FROM book_offsets WHERE book_id = ?", [(bid,) for bid in book_ids])
    
    cursor.executemany("""
        INSERT INTO book_offsets 
        (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, offsets_data_list)
    
    # Update total_pages and has_offsets for books
    from collections import Counter
    counts = Counter([o[0] for o in offsets_data_list])
    cursor.executemany("""
        UPDATE books SET total_pages = ?, has_offsets = 1 WHERE id = ?
    """, [(count, bid) for bid, count in counts.items()])
