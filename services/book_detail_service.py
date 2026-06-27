# -*- coding: utf-8 -*-
import os
import database
from utils.sort_helper import natural_sort_key
from utils.cover_helper import get_cover_image_with_t, resolve_series_cover

class BookDetailService:
    @staticmethod
    def get_media_detail(db_type, series_name, library_id='all', user_id=1):
        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()

        # 만약 library_id가 시스템 성격(all, history, favorite, home)이거나 없을 때
        # series_name이 중복 등록된 경우를 대비하여 해당 시리즈의 실제 library_id를 역추출합니다.
        if not library_id or library_id in ('all', 'history', 'favorite', 'home'):
            cursor.execute("SELECT library_id FROM books WHERE series_name = ? LIMIT 1", (series_name,))
            resolved_row = cursor.fetchone()
            if resolved_row and resolved_row['library_id']:
                library_id = resolved_row['library_id']

        use_lib_filter = library_id and library_id not in ('all', 'history', 'favorite', 'home')

        # 1. 시리즈 메타 정보 조회
        if use_lib_filter:
            cursor.execute("""
                SELECT author, publisher, link, score, summary
                FROM books
                WHERE series_name = ? AND library_id = ? AND (summary IS NOT NULL AND summary != '')
                LIMIT 1
            """, (series_name, library_id))
            meta_row = cursor.fetchone()
            if not meta_row:
                cursor.execute("""
                    SELECT author, publisher, link, score, summary
                    FROM books WHERE series_name = ? AND library_id = ? LIMIT 1
                """, (series_name, library_id))
                meta_row = cursor.fetchone()
        else:
            cursor.execute("""
                SELECT author, publisher, link, score, summary
                FROM books
                WHERE series_name = ? AND (summary IS NOT NULL AND summary != '')
                LIMIT 1
            """, (series_name,))
            meta_row = cursor.fetchone()
            if not meta_row:
                cursor.execute("""
                    SELECT author, publisher, link, score, summary
                    FROM books WHERE series_name = ? LIMIT 1
                """, (series_name,))
                meta_row = cursor.fetchone()

        # 2. 책 목록 조회
        if use_lib_filter:
            cursor.execute("""
                SELECT b.id, b.title, b.file_format, b.total_pages, b.has_offsets, b.cover_image, b.cover_updated_at,
                       b.file_path, p.pages_read, p.is_completed, b.is_favorite, b.library_id
                FROM books b
                LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
                WHERE b.series_name = ? AND b.library_id = ?
            """, (user_id, series_name, library_id))
        else:
            cursor.execute("""
                SELECT b.id, b.title, b.file_format, b.total_pages, b.has_offsets, b.cover_image, b.cover_updated_at,
                       b.file_path, p.pages_read, p.is_completed, b.is_favorite, b.library_id
                FROM books b
                LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
                WHERE b.series_name = ?
            """, (user_id, series_name))
        books_rows = cursor.fetchall()

        # 실제 covers 폴더 내 시리즈 이미지 갱신 타임스탬프 쿼리
        cursor.execute("SELECT MAX(cover_updated_at) AS latest_updated FROM books WHERE series_name = ?", (series_name,))
        time_row = cursor.fetchone()
        latest_updated = time_row['latest_updated'] if time_row else None
        conn.close()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        covers_dir = os.path.join(base_dir, 'covers')

        # library_id 정보 결정
        lib_id = None
        if use_lib_filter:
            lib_id = library_id
        elif books_rows:
            for b in books_rows:
                if b['library_id']:
                    lib_id = b['library_id']
                    break

        # 대표 커버 이미지 매핑 및 실존 여부 확인 (Fallback 적용)
        final_cover = resolve_series_cover(
            series_name=series_name,
            lib_id=lib_id,
            db_cover=books_rows[0]['cover_image'] if books_rows else None,
            covers_dir=covers_dir,
            conn=conn,
            candidates_rows=books_rows
        )

        def _val(row, key, default=''):
            return row[key] if row and row[key] else default

        meta = {
            'author'   : _val(meta_row, 'author',    '-'),
            'publisher': _val(meta_row, 'publisher', '-'),
            'link'     : _val(meta_row, 'link',       ''),
            'score'    : _val(meta_row, 'score',       0),
            'summary'  : _val(meta_row, 'summary', '등록된 설명이 없습니다.'),
            'cover_image': get_cover_image_with_t(final_cover, latest_updated)
        }

        books_list = []
        for b in books_rows:
            clean_title = b['title']
            if b['file_path']:
                filename_with_ext = os.path.basename(b['file_path'])
                clean_title, _ = os.path.splitext(filename_with_ext)
                
            books_list.append({
                'id'          : b['id'],
                'title'       : clean_title,
                'file_format' : b['file_format'],
                'total_pages' : b['total_pages'],
                'has_offsets' : b['has_offsets'] or 0,
                'cover_image' : get_cover_image_with_t(b['cover_image'], b['cover_updated_at']),
                'file_path'   : b['file_path'] or '',
                'pages_read'  : b['pages_read']  or 0,
                'is_completed': b['is_completed'] or 0,
                'is_favorite' : b['is_favorite'] or 0,
            })
        
        # 부모 디렉토리 기반 단행본 격리 필터
        if books_list:
            first_file_path = books_list[0]['file_path']
            if first_file_path:
                target_dir = os.path.dirname(first_file_path)
                books_list = [bk for bk in books_list if bk['file_path'] and os.path.dirname(bk['file_path']) == target_dir]
                
        books_list.sort(key=lambda x: natural_sort_key(x['title']))
        return meta, books_list

    @staticmethod
    def update_media_detail(db_type, series_name, author, publisher, summary, link, cover_file=None):
        import hashlib
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        try:
            # 1. 해당 시리즈에 속한 도서의 library_id와 대표 book 레코드 1개 조회
            cursor.execute("SELECT library_id FROM books WHERE series_name = ? LIMIT 1", (series_name,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False, '해당 시리즈에 속한 도서를 찾을 수 없습니다.'
            
            library_id = row['library_id']
            
            # 2. 커버 이미지 파일 업로드 처리
            if cover_file:
                # covers 디렉터리 경로 계산
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                covers_dir = os.path.join(base_dir, 'covers')
                
                # library_id별 서브폴더 보장
                target_covers_dir = os.path.join(covers_dir, str(library_id)) if library_id is not None else covers_dir
                os.makedirs(target_covers_dir, exist_ok=True)
                
                # 시리즈명 해시를 따서 series_{series_hash}.jpg 규격으로 생성
                series_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()
                cover_filename = f"series_{series_hash}.jpg"
                dest_path = os.path.join(target_covers_dir, cover_filename)
                
                # 업로드된 파일 저장 (물리적 덮어쓰기 강제 진행)
                cover_file.save(dest_path)
                print(f"[BookDetailService] 시리즈 대표 표지 수동 업로드 완료: {dest_path}")
            
            # 3. 시리즈에 속하는 모든 도서 레코드 메타데이터 일괄 업데이트
            # (수정 시 cover_updated_at을 CURRENT_TIMESTAMP로 갱신하여 브라우저 캐시 버스팅 보장)
            cursor.execute("""
                UPDATE books
                SET author = ?,
                    publisher = ?,
                    summary = ?,
                    link = ?,
                    cover_updated_at = CURRENT_TIMESTAMP
                WHERE series_name = ?
            """, (author, publisher, summary, link, series_name))
            
            conn.commit()
            conn.close()
            return True, f'"{series_name}" 메타정보가 성공적으로 수정되었습니다.'
        except Exception as e:
            if conn:
                conn.close()
            print(f"[BookDetailService] 메타정보 수정 에러: {e}")
            return False, f'DB 업데이트 오류: {str(e)}'
