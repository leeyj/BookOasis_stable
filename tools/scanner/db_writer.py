# -*- coding: utf-8 -*-
import os

def update_book_metadata(cursor, full_path, cover_image, merged_meta):
    """기존 도서 정보 및 로컬 메타데이터 병합 업데이트 실행"""
    cursor.execute("""
        UPDATE books SET 
            cover_image  = COALESCE(NULLIF(?, ''), cover_image),
            cover_updated_at = CASE WHEN ? != '' AND ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE cover_updated_at END,
            author       = COALESCE(NULLIF(?, ''), author),
            publisher    = COALESCE(NULLIF(?, ''), publisher),
            link         = COALESCE(NULLIF(?, ''), link),
            score        = CASE WHEN ? != 0 THEN ? ELSE score END,
            summary      = COALESCE(NULLIF(?, ''), summary),
            release_date = COALESCE(NULLIF(?, ''), release_date)
        WHERE file_path = ?
    """, (
        cover_image,
        cover_image, cover_image,
        merged_meta['author'],
        merged_meta['publisher'],
        merged_meta['link'],
        merged_meta['score'], merged_meta['score'],
        merged_meta['summary'],
        merged_meta['release_date'],
        full_path
    ))

def insert_new_book(cursor, library_id, filename, series_name, cover_image, merged_meta):
    """신규 도서 정보 DB 인서트 및 도서 ID(book_id) 반환"""
    title, _ = os.path.splitext(filename)
    file_format = os.path.splitext(filename)[1].replace('.', '').lower()
    full_path = os.path.join(os.path.dirname(cover_image) if cover_image and '/' in cover_image else '', filename) # 실제 경로는 외부에서 오버라이드되거나 전달받음.
    
    # 주의: full_path는 외부에서 정확히 넘겨받는 편이 좋으므로 함수의 인수로 직접 전달하게 수정하는 것이 안전함.
    # 함수 정의를 아래와 같이 보완하자.
    pass

def insert_new_book_v2(cursor, library_id, full_path, filename, file_format, series_name, cover_image, merged_meta):
    """신규 도서 정보 DB 인서트 및 도서 ID(book_id) 반환"""
    title, _ = os.path.splitext(filename)
    cursor.execute("""
        INSERT INTO books 
        (library_id, title, series_name, author, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        library_id, 
        title, 
        series_name, 
        merged_meta['author'], 
        full_path, 
        file_format, 
        0, 
        cover_image,
        merged_meta['publisher'],
        merged_meta['link'],
        merged_meta['score'],
        merged_meta['summary'],
        merged_meta['release_date']
    ))
    return cursor.lastrowid

def save_book_offsets(cursor, book_id, filename, offsets_data):
    """오프셋 정보 DB 일괄 벌크 저장 및 books 테이블 요약 갱신"""
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
    print(f"[Scanner-Offset] '{filename}' 오프셋 DB 색인 완료 ({len(bulk_data)} 페이지)")
