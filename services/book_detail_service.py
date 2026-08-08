# -*- coding: utf-8 -*-
import os
# pyrefly: ignore [missing-import]
from repositories.audiobook_repository import AudiobookRepository
from repositories.book_repository import BookRepository 
from utils.sort_helper import natural_sort_key
from utils.cover_helper import get_cover_image_with_t, resolve_series_cover, invalidate_series_cover_cache
from utils.redis_helper import redis_delete_pattern

class BookDetailService:
    @staticmethod
    def get_media_detail(db_type, series_name, library_id='all', user_id=1, role=None, restrict_same_directory=True, representative_book_id=None):
        if db_type == 'audiobook':
            audiobook_row = None
            if representative_book_id:
                try:
                    audiobook_row = AudiobookRepository.get_audiobook_by_id(int(representative_book_id))
                except Exception:
                    pass
            
            if not audiobook_row and series_name:
                audiobook_row = AudiobookRepository.get_audiobook_by_series_or_folder_name(series_name)

            if not audiobook_row:
                audiobook_row = AudiobookRepository.get_first_audiobook()

            if not audiobook_row:
                return {'series_name': series_name, 'author': '-', 'publisher': '-', 'summary': '등록된 오디오북이 없습니다.', 'cover_image': ''}, []

            aid = audiobook_row['id']
            
            # 사용자 진행도
            prog_row = AudiobookRepository.get_audiobook_progress(aid, user_id)
            current_track_id = prog_row['current_track_id'] if prog_row else None
            current_time = prog_row['current_time'] if prog_row else 0.0
            total_progress_pct = prog_row['total_progress_pct'] if (prog_row and 'total_progress_pct' in prog_row) else 0.0
            is_completed = prog_row['is_completed'] if (prog_row and 'is_completed' in prog_row) else 0

            # 트랙 목록
            track_rows = AudiobookRepository.get_audiobook_tracks(aid)
            track_progress = AudiobookRepository.get_audiobook_track_progress(aid, user_id)
            current_track_number = None
            if current_track_id is not None:
                current_track = next((row for row in track_rows if int(row['id']) == int(current_track_id)), None)
                if current_track:
                    current_track_number = int(current_track.get('track_number') or 0)

            meta = {
                'id': aid,
                'series_name': audiobook_row['title'],
                'series_alias': '',
                'author': audiobook_row['author'] or '-',
                'isbn': '',
                'web_id': audiobook_row['web_id'] or '',
                'publisher': audiobook_row['publisher'] or '-',
                'code': audiobook_row['code'] or '',
                'ratings': audiobook_row['ratings'] or 0.0,
                'summary': audiobook_row['description'] or audiobook_row['author_intro'] or '등록된 설명이 없습니다.',
                'cover_image': f"/api/media/audiobooks/{aid}/cover",
                'total_duration': audiobook_row['total_duration'] or 0.0,
                'total_tracks': audiobook_row['total_tracks'] or len(track_rows),
                'file_type': audiobook_row['file_type'] or 'multi',
                'is_favorite': audiobook_row['is_favorite'] or 0,
                'current_track_id': current_track_id,
                'current_time': current_time,
                'total_progress_pct': total_progress_pct,
                'is_completed': is_completed,
                'metadata_locked': 0
            }

            books_list = []
            for t in track_rows:
                dur_sec = t['duration'] or 0.0
                mins = int(dur_sec // 60)
                secs = int(dur_sec % 60)
                time_str = f"{mins:02d}:{secs:02d}"
                saved_track_progress = track_progress.get(int(t['id']))
                if is_completed:
                    track_progress_pct = 100.0
                    is_track_completed = 1
                elif saved_track_progress:
                    track_progress_pct = float(saved_track_progress.get('progress_pct') or 0.0)
                    is_track_completed = 1 if track_progress_pct >= 95.0 else 0
                elif current_track_number is not None and int(t.get('track_number') or 0) < current_track_number:
                    track_progress_pct = 100.0
                    is_track_completed = 1
                elif current_track_id is not None and int(t['id']) == int(current_track_id) and float(dur_sec or 0.0) > 0:
                    track_progress_pct = min(100.0, (float(current_time or 0.0) / float(dur_sec)) * 100.0)
                    is_track_completed = 1 if track_progress_pct >= 95.0 else 0
                else:
                    track_progress_pct = 0.0
                    is_track_completed = 0

                books_list.append({
                    'id': t['id'],
                    'audiobook_id': aid,
                    'track_number': t['track_number'],
                    'track_code': t['track_code'] or str(t['track_number']),
                    'title': t['filename'],
                    'file_format': t['format'] or 'mp3',
                    'duration': dur_sec,
                    'time_str': time_str,
                    'track_progress_pct': track_progress_pct,
                    'is_track_completed': is_track_completed,
                    'file_size': t['file_size'] or 0,
                    'file_path': t['file_path'],
                    'total_pages': mins if mins > 0 else 1,
                    'cover_image': meta['cover_image'],
                    'is_completed': 1 if prog_row and prog_row['is_completed'] else 0,
                    'is_favorite': meta['is_favorite'],
                })

            return meta, books_list

        enforce_permission = (role != 'admin' and bool(user_id))

        # 권한 제어 절 정보 결정
        if enforce_permission:
            perm_clause = (
                " AND EXISTS ("
                "SELECT 1 FROM user_category_permissions p "
                "WHERE p.library_id = books.library_id AND p.user_id = ? AND p.has_access = 1"
                ")"
            )
            perm_clause_b = (
                " AND EXISTS ("
                "SELECT 1 FROM user_category_permissions p "
                "WHERE p.library_id = b.library_id AND p.user_id = ? AND p.has_access = 1"
                ")"
            )
            perm_params = [user_id]
        else:
            perm_clause = ''
            perm_clause_b = ''
            perm_params = []

        def _comparison_dir(path, file_format):
            normalized = (path or '').replace('\\', '/')
            if not normalized:
                return ''
            if str(file_format or '').lower() == 'imgdir' and normalized.endswith('/__folder__.imgdir'):
                return os.path.dirname(os.path.dirname(path))
            return os.path.dirname(path)

        anchor_dir = None

        if representative_book_id:
            try:
                rep_id_int = int(representative_book_id)
                rep_row = BookRepository.get_representative_book_info(db_type, rep_id_int, perm_clause, perm_params)
                if rep_row:
                    series_name = rep_row['series_name'] or series_name
                    library_id = rep_row['library_id'] if rep_row['library_id'] is not None else library_id
                    anchor_dir = _comparison_dir(rep_row['file_path'], rep_row['file_format'])
            except (ValueError, TypeError):
                pass

        if series_name:
            series_name = BookRepository.resolve_series_name_by_alias(db_type, series_name, perm_clause, perm_params)

        if not library_id or library_id in ('all', 'history', 'favorite', 'home'):
            resolved_lib_id = BookRepository.resolve_series_library_id(db_type, series_name, perm_clause, perm_params)
            if resolved_lib_id:
                library_id = resolved_lib_id

        use_lib_filter = library_id and library_id not in ('all', 'history', 'favorite', 'home')

        # 1. 시리즈 메타 정보 조회
        meta_row = BookRepository.get_series_meta(db_type, series_name, library_id, perm_clause, perm_params)

        # 2. 책 목록 조회
        books_rows = BookRepository.get_books_by_series_detail(db_type, series_name, library_id, user_id, perm_clause_b, perm_params)

        # 실제 covers 폴더 내 시리즈 이미지 갱신 타임스탬프 쿼리
        latest_updated = BookRepository.get_series_latest_updated(db_type, series_name, perm_clause, perm_params)

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
            conn=None,
            candidates_rows=books_rows
        )

        def _val(row, key, default=''):
            return row[key] if row and row[key] else default

        meta = {
            'series_name': series_name,
            'series_alias': _val(meta_row, 'series_alias', ''),
            'author'   : _val(meta_row, 'author',    '-'),
            'isbn'     : _val(meta_row, 'isbn',      ''),
            'web_id'   : '',
            'publisher': _val(meta_row, 'publisher', '-'),
            'link'     : _val(meta_row, 'link',       ''),
            'score'    : _val(meta_row, 'score',       0),
            'summary'  : _val(meta_row, 'summary', '등록된 설명이 없습니다.'),
            'genre'    : _val(meta_row, 'genre',      ''),
            'tags'     : _val(meta_row, 'tags',       ''),
            'metadata_locked': meta_row.get('metadata_locked', 0) if meta_row else (1 if any(b.get('metadata_locked', 0) == 1 for b in books_rows) else 0),
            'cover_image': get_cover_image_with_t(final_cover, latest_updated)
        }

        books_list = []
        for b in books_rows:
            clean_title = b['title']
            file_format = (b['file_format'] or '').lower()
            if file_format == 'imgdir' and b['file_path']:
                clean_title = os.path.basename(os.path.dirname(b['file_path'])) or clean_title
            elif b['file_path']:
                filename_with_ext = os.path.basename(b['file_path'])
                clean_title, _ = os.path.splitext(filename_with_ext)
                
            total_pages = b['total_pages'] or 0
            has_offsets_val = b.get('has_offsets', 0)
            if total_pages > 0 or (b.get('file_format') or '').lower() not in ('zip', 'cbz'):
                has_offsets_val = 1

            books_list.append({
                'id'          : b['id'],
                'title'       : clean_title,
                'title_alias' : b.get('title_alias', '') or '',
                'file_format' : b['file_format'],
                'total_pages' : total_pages,
                'has_offsets' : has_offsets_val,
                'cover_image' : get_cover_image_with_t(b['cover_image'], b['cover_updated_at']),
                'file_path'   : b['file_path'] or '',
                'pages_read'  : b['pages_read']  or 0,
                'is_completed': b['is_completed'] or 0,
                'is_favorite' : b['is_favorite'] or 0,
                'last_read_at': b['last_read_at'] or '',
                'metadata_locked': b.get('metadata_locked', 0),
            })
        
        # 부모 디렉토리 기반 단행본 격리 필터
        if restrict_same_directory and books_list:
            target_dir = anchor_dir
            if not target_dir:
                target_dir = _comparison_dir(books_list[0]['file_path'], books_list[0]['file_format'])
            if target_dir:
                books_list = [
                    bk for bk in books_list
                    if bk['file_path'] and _comparison_dir(bk['file_path'], bk['file_format']) == target_dir
                ]
                
        books_list.sort(key=lambda x: natural_sort_key(x['title']))
        return meta, books_list

    @staticmethod
    def update_media_detail(db_type, series_name, author, isbn, publisher, summary, link, genre='', tags='', cover_file=None, series_alias=None):
        import hashlib

        if db_type == 'audiobook':
            try:
                cover_image_url = None
                if cover_file:
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    covers_dir = os.path.join(base_dir, 'covers')
                    target_covers_dir = os.path.join(covers_dir, 'audiobook')
                    os.makedirs(target_covers_dir, exist_ok=True)

                    series_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()
                    cover_filename = f"audiobook_series_{series_hash}.jpg"
                    dest_path = os.path.join(target_covers_dir, cover_filename)
                    cover_file.save(dest_path)
                    cover_image_url = f"/api/media/covers/audiobook/{cover_filename}"

                AudiobookRepository.update_media_detail(series_name, author, isbn, publisher, summary, cover_image_url=cover_image_url)
                
                # In-Memory 및 Redis 캐시 파기
                invalidate_series_cover_cache(db_type='audiobook', lib_id=None, series_name=series_name)
                try:
                    redis_delete_pattern("cache:history*:audiobook:*")
                    redis_delete_pattern("cache:recent_added*:audiobook:*")
                except Exception as cache_err:
                    print(f"[BookDetailService WARNING] 오디오북 레디스 캐시 소거 실패: {cache_err}")

                return True, f'"{series_name}" 메타정보가 성공적으로 수정되었습니다.'
            except Exception as e:
                print(f"[BookDetailService] 오디오북 메타정보 수정 에러: {e}")
                return False, f'DB 업데이트 오류: {str(e)}'
        
        # 1. 해당 시리즈에 속한 도서의 library_id와 대표 book 레코드 1개 조회
        from repositories.book_repository import BookRepository
        library_id = BookRepository.resolve_series_library_id(db_type, series_name, '', [])
        if library_id is None:
            return False, '해당 시리즈에 속한 도서를 찾을 수 없습니다.'
        
        try:
            cover_image_url = None
            # 2. 커버 이미지 파일 업로드 처리
            if cover_file:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                covers_dir = os.path.join(base_dir, 'covers')
                
                target_covers_dir = os.path.join(covers_dir, str(library_id))
                os.makedirs(target_covers_dir, exist_ok=True)
                
                series_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()
                cover_filename = f"series_{series_hash}.jpg"
                dest_path = os.path.join(target_covers_dir, cover_filename)
                
                cover_file.save(dest_path)
                cover_image_url = f"/api/media/covers/{library_id}/{cover_filename}"
                print(f"[BookDetailService] 시리즈 대표 표지 수동 업로드 완료: {dest_path} -> {cover_image_url}")
            
            # 3. 시리즈 메타 정보 일괄 업데이트
            BookRepository.update_media_detail(db_type, series_name, author, isbn, publisher, summary, link, genre, tags, series_alias=series_alias, cover_image_url=cover_image_url)
            
            # 4. In-Memory 표지 캐시 및 Redis 캐시 무효화
            invalidate_series_cover_cache(db_type=db_type, lib_id=library_id, series_name=series_name)
            invalidate_series_cover_cache(db_type=db_type)
            try:
                redis_delete_pattern(f"cache:history*:{db_type}:*")
                redis_delete_pattern(f"cache:recent_added*:{db_type}:*")
            except Exception as cache_err:
                print(f"[BookDetailService WARNING] 레디스 캐시 소거 실패: {cache_err}")

            return True, f'"{series_name}" 메타정보가 성공적으로 수정되었습니다.'
        except Exception as e:
            print(f"[BookDetailService] 메타정보 수정 에러: {e}")
            return False, f'DB 업데이트 오류: {str(e)}'
