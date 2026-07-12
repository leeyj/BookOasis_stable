# -*- coding: utf-8 -*-
import os

def update_book_metadata(cursor, full_path, cover_image, merged_meta, series_name=''):
    """Execute merge update for existing book info and local metadata"""
    cursor.execute("""
        UPDATE books SET 
            series_name  = CASE WHEN 1=0 THEN ? ELSE series_name END,
            cover_image  = COALESCE(NULLIF(?, ''), cover_image),
            cover_updated_at = CASE WHEN ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
            author       = COALESCE(NULLIF(?, ''), author),
            publisher    = COALESCE(NULLIF(?, ''), publisher),
            link         = COALESCE(NULLIF(?, ''), link),
            score        = CASE WHEN ? != 0 THEN ? ELSE score END,
            summary      = COALESCE(NULLIF(?, ''), summary),
            release_date = COALESCE(NULLIF(?, ''), release_date),
            genre        = COALESCE(NULLIF(?, ''), genre),
            tags         = COALESCE(NULLIF(?, ''), tags)
        WHERE file_path = ?
    """, (
        series_name,
        cover_image,
        cover_image, cover_image,
        merged_meta['author'],
        merged_meta['publisher'],
        merged_meta['link'],
        merged_meta['score'], merged_meta['score'],
        merged_meta['summary'],
        merged_meta['release_date'],
        merged_meta.get('genre', ''),
        merged_meta.get('tags', ''),
        full_path
    ))

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
        (library_id, title, series_name, author, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date, genre, tags, file_mtime, file_size) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        library_id, 
        title, 
        series_name, 
        merged_meta['author'], 
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

def bulk_update_books(cursor, update_data_list):
    """Bulk update existing books"""
    if not update_data_list: return
    cursor.executemany("""
        UPDATE books SET 
            series_name  = CASE WHEN 1=0 THEN ? ELSE series_name END,
            cover_image  = COALESCE(NULLIF(?, ''), cover_image),
            cover_updated_at = CASE WHEN ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
            author       = COALESCE(NULLIF(?, ''), author),
            publisher    = COALESCE(NULLIF(?, ''), publisher),
            link         = COALESCE(NULLIF(?, ''), link),
            score        = CASE WHEN ? != 0 THEN ? ELSE score END,
            summary      = COALESCE(NULLIF(?, ''), summary),
            release_date = COALESCE(NULLIF(?, ''), release_date),
            genre        = COALESCE(NULLIF(?, ''), genre),
            tags         = COALESCE(NULLIF(?, ''), tags),
            file_mtime   = ?,
            file_size    = ?
        WHERE file_path = ?
    """, update_data_list)

def bulk_insert_books(cursor, insert_data_list):
    """Bulk insert new books"""
    if not insert_data_list: return
    cursor.executemany("""
        INSERT OR IGNORE INTO books 
        (library_id, title, series_name, author, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date, genre, tags, file_mtime, file_size) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
