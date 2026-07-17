# -*- coding: utf-8 -*-
import os
import sys

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import gc
from tools.scanner.metadata import parse_info_xml, parse_kavita_yaml, parse_series_json, parse_comicinfo_from_cbz, merge_local_metadata, is_consonant_folder
from tools.scanner.cover import get_series_cover_fallback, get_imgdir_cover, extract_cover_from_b64, download_cover_from_url
from tools.scanner.offset import collect_zip_offsets_data

SUPPORTED_FORMATS = ('.zip', '.cbz', '.epub', '.pdf', '.txt')
SUPPORTED_IMAGE_FORMATS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
IMGDIR_VIRTUAL_FILENAME = '__folder__.imgdir'


def _normalize_series_text(name):
    """Normalize folder-derived series text."""
    if not name:
        return ''
    import re
    return re.sub(r'^\[(?:단행|연재|소설|만화|웹툰|일반)\]\s*', '', str(name)).strip()


def process_folder_task(root, files, force, db_meta_full, db_offsets_cached, db_folder_mtimes, is_remote=False, library_id=None, db_files_cache=None, library_root=None):
    """Independent I/O scan task per folder (DB independent, pure FS/I/O scaling)"""
    root = root.replace('\\', '/').strip()
    print(f"[Scanner-DEBUG-Task] 📂 entering process_folder_task - folder: '{root}'")
    
    media_files = [f for f in files if f.lower().endswith(SUPPORTED_FORMATS)]
    image_files = [f for f in files if f.lower().endswith(SUPPORTED_IMAGE_FORMATS)]
    has_imgdir_candidate = bool(image_files) and not media_files
    if not media_files and not has_imgdir_candidate:
        print(f"[Scanner-DEBUG-Task] 📁 Unsupported folder (skip) - folder: '{root}'")
        return None

    # 1. Pre-check if metadata file exists
    has_yaml = any(f.lower() == 'kavita.yaml' for f in files)
    has_xml = any(f.lower() == 'info.xml' for f in files)
    
    dir_mtime = None
    meta_mtime = None
    
    try:
        dir_mtime = os.path.getmtime(root)
        meta_mtimes_list = []
        if has_yaml:
            yaml_file = next(f for f in files if f.lower() == 'kavita.yaml')
            meta_mtimes_list.append(os.path.getmtime(os.path.join(root, yaml_file)))
        if has_xml:
            xml_file = next(f for f in files if f.lower() == 'info.xml')
            meta_mtimes_list.append(os.path.getmtime(os.path.join(root, xml_file)))
        
        if meta_mtimes_list:
            meta_mtime = max(meta_mtimes_list)
        else:
            meta_mtime = 0.0
    except Exception as e:
        print(f"[Scanner-DEBUG-Task] ⚠️ Failed to get mtime for folder '{root}': {e}")
        dir_mtime = None

    # 2. Early skip if files are unchanged (mtime & size match DB cache)
    skipped_files = set()
    imgdir_skip = False
    imgdir_virtual_path = os.path.join(root, IMGDIR_VIRTUAL_FILENAME)
    if not force and db_files_cache:
        for filename in media_files:
            full_path = os.path.join(root, filename)
            if full_path in db_files_cache:
                try:
                    p_mtime = os.path.getmtime(full_path)
                    p_size = os.path.getsize(full_path)
                    c_mtime, c_size = db_files_cache[full_path]
                    
                    if int(c_mtime) == int(p_mtime) and c_size == p_size:
                        file_ext = os.path.splitext(filename)[1].lower()
                        if file_ext in ('.zip', '.cbz') and not is_remote and full_path not in db_offsets_cached:
                            continue
                        # TXT는 오프셋/표지 강제 재시도가 필요 없으므로 mtime/size 동일 시 바로 스킵
                        if file_ext == '.txt':
                            skipped_files.add(filename)
                            continue
                        if full_path not in db_meta_full:
                            continue
                        skipped_files.add(filename)
                except Exception:
                    # 원격 드라이브이고 이미 DB 캐시(mtime, 메타데이터, 커버)가 있는 경우 예외가 나더라도 스킵 처리
                    if is_remote and full_path in db_meta_full:
                        c_mtime, c_size = db_files_cache[full_path]
                        if c_mtime > 0.0:
                            skipped_files.add(filename)

        if has_imgdir_candidate and imgdir_virtual_path in db_files_cache:
            try:
                p_mtime = os.path.getmtime(root)
                p_size = sum(
                    os.path.getsize(os.path.join(root, f))
                    for f in image_files
                    if os.path.exists(os.path.join(root, f))
                )
                c_mtime, c_size = db_files_cache[imgdir_virtual_path]
                if int(c_mtime) == int(p_mtime) and int(c_size) == int(p_size):
                    imgdir_skip = True
            except Exception:
                imgdir_skip = False

        all_files_skipped = (
            len(skipped_files) == len(media_files)
            and (not has_imgdir_candidate or imgdir_skip)
        )
        if all_files_skipped:
            if not has_yaml and not has_xml:
                print(f"[Scanner-DEBUG-Task] ⚡ [Ultra-fast skip] All files unchanged (mtime/size match) - folder: '{root}'")
                return None
            else:
                if dir_mtime is not None:
                    cached_mtimes = db_folder_mtimes.get(root)
                    if cached_mtimes:
                        c_dir_mtime, c_meta_mtime = cached_mtimes
                        if int(c_dir_mtime) == int(dir_mtime) and int(c_meta_mtime) == int(meta_mtime):
                            print(f"[Scanner-DEBUG-Task] ⚡ [Ultra-fast skip] All files unchanged and meta mtime unchanged - folder: '{root}'")
                            return None
                        else:
                            print(f"[Scanner-DEBUG-Task] ⚠️ [Ultra-fast skip failed] mtime changed (dir: {int(c_dir_mtime)}->{int(dir_mtime)}, meta: {int(c_meta_mtime)}->{int(meta_mtime)}) - folder: '{root}'")

    # 일반 파일(archive/txt/pdf/epub)은 "현재 폴더명"을 시리즈로 사용한다.
    # 즉, 라이브러리 루트와 현재 폴더 사이의 중간 경로는 모두 무시한다.
    series_name = _normalize_series_text(os.path.basename(root.rstrip('/')))

    print(f"[Scanner-DEBUG-Task]   - Metadata YAML/XML/JSON load started")
    merged_meta = merge_local_metadata(root, files=files, is_remote=is_remote)
    print(f"[Scanner-DEBUG-Task]   - Metadata load completed")

    meta_has_data = bool(
        merged_meta['author'] or merged_meta['publisher'] or
        merged_meta['summary'] or merged_meta['release_date'] or
        merged_meta['cover_b64_map']
    )

    is_series_folder = bool(merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
    is_json_only_webtoon = bool(not merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
    series_cover_url = merged_meta.get('cover_image_url', '') if is_json_only_webtoon else ''
    shared_cover_image = None

    import zipfile
    results = []
    errors = []
    for filename in media_files:
        full_path = os.path.join(root, filename)
        _, ext = os.path.splitext(filename)
        file_format = ext.replace('.', '').lower()

        skip = False
        if not force and not meta_has_data and full_path in db_meta_full and full_path in db_offsets_cached:
            skip = True
        elif filename in skipped_files:
            skip = True

        cover_image = None
        offsets_data = []
        offset_only = False  # Cover/meta complete, offset-only fast path flag

        if skip:
            pass  # Fully cached book — skip all processing

        elif (
            not force and
            not meta_has_data and
            full_path in db_meta_full and
            full_path not in db_offsets_cached and
            file_format in ('zip', 'cbz') and
            not is_remote
        ):
            # ── [Offset-only Fast Path] ──
            # If existing book has cover/meta but no offset:
            # Completely skip ComicInfo parsing and cover extraction pipeline
            # Only read ZIP central directory (collect offsets) - Minimize I/O
            offset_only = True
            try:
                offsets_data = collect_zip_offsets_data(full_path)
                if offsets_data:
                    print(f"[Scanner-DEBUG-Task] ⚡ [Offset-only] '{filename}' ({len(offsets_data)}p)")
                else:
                    print(f"[Scanner-DEBUG-Task] ⚡ [Offset-only] Skip ZIP without images: '{filename}'")
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ Offset-only collection failed: '{filename}' - {e}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'OffsetError',
                    'message': f"Offset-only collection failed: {str(e)}"
                })

        else:
            # ── [General Path] Cover extraction + Offset collection ──
            print(f"[Scanner-DEBUG-Task]   - File processing started: '{filename}'")
            try:
                # [ComicInfo.xml parsing] If local file and CBZ format, extract metadata internally
                # Skip remote paths due to high I/O cost -> delegated to Lazy Scanner
                if not is_remote and file_format in ('cbz', 'zip') and (
                    not merged_meta['author'] or not merged_meta['summary'] or not merged_meta.get('genre') or not merged_meta.get('tags')
                ):
                    try:
                        comicinfo = parse_comicinfo_from_cbz(full_path)
                        if comicinfo['author'] and not merged_meta['author']:
                            merged_meta['author'] = comicinfo['author']
                            print(f"[Scanner-DEBUG-Task]     - ComicInfo.xml author fallback: {comicinfo['author']}")
                        if comicinfo['publisher'] and not merged_meta['publisher']:
                            merged_meta['publisher'] = comicinfo['publisher']
                        if comicinfo['summary'] and not merged_meta['summary']:
                            merged_meta['summary'] = comicinfo['summary']
                        if comicinfo['release_date'] and not merged_meta['release_date']:
                            merged_meta['release_date'] = comicinfo['release_date']
                        if comicinfo.get('genre') and not merged_meta.get('genre'):
                            merged_meta['genre'] = comicinfo['genre']
                        if comicinfo.get('tags') and not merged_meta.get('tags'):
                            merged_meta['tags'] = comicinfo['tags']
                    except Exception as ce:
                        print(f"[Scanner-DEBUG-Task]     - ComicInfo.xml parsing skipped: {ce}")

                # Convert keys to lowercase to prevent case issues in Linux
                filename_lower = filename.lower()
                b64_keys_lower = {k.lower(): v for k, v in merged_meta['cover_b64_map'].items()}
                
                if filename_lower in b64_keys_lower:
                    print(f"[Scanner-DEBUG-Task]     - YAML b64 cover decoding started")
                    cover_image = extract_cover_from_b64(full_path, b64_keys_lower[filename_lower], force=force, library_id=library_id)
                
                if not cover_image:
                    if (is_series_folder or is_json_only_webtoon) and shared_cover_image:
                        print(f"[Scanner-DEBUG-Task]     - Series cover (thumbnail) cloned")
                        cover_image = shared_cover_image
                    elif is_json_only_webtoon and series_cover_url:
                        print(f"[Scanner-DEBUG-Task]     - series.json URL cover download started")
                        cover_image = download_cover_from_url(full_path, series_cover_url, force=force, library_id=library_id)
                    else:
                        print(f"[Scanner-DEBUG-Task]     - Fallback cover extraction started")
                        cover_image = get_series_cover_fallback(series_name, root, force=force, is_remote=is_remote, filename=filename, file_path=full_path, library_id=library_id)
                
                # Save first successful cover as shared thumbnail for series folder regardless of source
                if (is_series_folder or is_json_only_webtoon) and cover_image and not shared_cover_image:
                    shared_cover_image = cover_image

                # Real-time check if extracted cover is 0 bytes
                if cover_image:
                    cover_filepath = os.path.join(MEDIA_SERVER_DIR, 'covers', cover_image)
                    if os.path.exists(cover_filepath) and os.path.getsize(cover_filepath) == 0:
                        print(f"[Scanner-DEBUG-Task] ⚠️ Extracted cover file is 0 bytes: {cover_filepath}")
                        try:
                            os.remove(cover_filepath)
                        except Exception:
                            pass
                        cover_image = None  # Invalidate to include in error report collection
                
                # Log to error list if Zip/EPUB format but no cover acquired
                if not cover_image and file_format in ('zip', 'cbz', 'epub'):
                    if is_remote:
                        print(f"[Scanner-DEBUG-Task] ⚠️ No cover for remote archive (deferred to lazy scanner): '{filename}'")
                    else:
                        errors.append({
                            'file_path': full_path,
                            'filename': filename,
                            'error_type': 'NoCover',
                            'message': 'ERR_NO_COVER'
                        })
            except zipfile.BadZipFile as bzf:
                print(f"[Scanner-DEBUG-Task] ❌ BadZipFile detected: '{filename}' - {bzf}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'BadZipFile',
                    'message': str(bzf)
                })
            except ValueError as ve:
                print(f"[Scanner-DEBUG-Task] ❌ ValueError detected: '{filename}' - {ve}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'NoCover',
                    'message': str(ve)
                })
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ General exception detected: '{filename}' - {e}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'Exception',
                    'message': str(e)
                })

            try:
                if file_format in ('zip', 'cbz') and (force or full_path not in db_offsets_cached):
                    if is_remote:
                        offsets_data = []
                    else:
                        print(f"[Scanner-DEBUG-Task]     - Offset analysis started: '{filename}'")
                        offsets_data = collect_zip_offsets_data(full_path)
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ Offset analysis failed: '{filename}' - {e}")
                if not any(err['file_path'] == full_path for err in errors):
                    errors.append({
                        'file_path': full_path,
                        'filename': filename,
                        'error_type': 'OffsetAnalysis',
                        'message': f"ERR_OFFSET_FAIL: {str(e)}"
                    })
            print(f"[Scanner-DEBUG-Task]   - File processing completed: '{filename}'")

        f_mtime = 0.0
        f_size = 0
        try:
            f_mtime = os.path.getmtime(full_path)
            f_size = os.path.getsize(full_path)
        except Exception:
            pass

        results.append({
            'full_path': full_path,
            'filename': filename,
            'file_format': file_format,
            'series_name': series_name,
            'title': None,
            'cover_image': cover_image,
            'offsets_data': offsets_data,
            'skip': skip,
            'offset_only': offset_only,  # Whether it's offset-only fast path
            'file_mtime': f_mtime,
            'file_size': f_size,
        })

    if has_imgdir_candidate:
        # 이미지 폴더(imgdir)는 "현재 폴더=책", "부모 폴더=시리즈" 규칙을 사용한다.
        parent_folder = os.path.basename(os.path.dirname(root.rstrip('/')))
        imgdir_series_name = _normalize_series_text(parent_folder) if parent_folder else series_name
        imgdir_title = os.path.basename(root)
        imgdir_cover = None
        if not imgdir_skip:
            try:
                imgdir_cover = get_imgdir_cover(root, imgdir_virtual_path, force=force, library_id=library_id)
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ IMGDIR cover extraction failed: '{root}' - {e}")
                errors.append({
                    'file_path': imgdir_virtual_path,
                    'filename': IMGDIR_VIRTUAL_FILENAME,
                    'error_type': 'NoCover',
                    'message': f"IMGDIR cover extraction failed: {str(e)}"
                })

        f_mtime = 0.0
        f_size = 0
        try:
            f_mtime = os.path.getmtime(root)
            f_size = sum(
                os.path.getsize(os.path.join(root, f))
                for f in image_files
                if os.path.exists(os.path.join(root, f))
            )
        except Exception:
            pass

        results.append({
            'full_path': imgdir_virtual_path,
            'filename': IMGDIR_VIRTUAL_FILENAME,
            'file_format': 'imgdir',
            'series_name': imgdir_series_name,
            'title': imgdir_title,
            'cover_image': imgdir_cover,
            'offsets_data': [],
            'skip': imgdir_skip,
            'offset_only': False,
            'file_mtime': f_mtime,
            'file_size': f_size,
        })

    # Clear references to large base64 maps used to free memory
    merged_meta.pop('cover_b64_map', None)

    gc.collect()
    print(f"[Scanner-DEBUG-Task] 📁 process_folder_task completed - folder: '{root}'")
    return {
        'root': root,
        'merged_meta': merged_meta,
        'results': results,
        'errors': errors,
        'dir_mtime': dir_mtime,
        'meta_mtime': meta_mtime
    }

def process_folder_covers(parent_dir, folder_rows, is_remote, library_id):
    """Extract covers by folder. Share to rest if first book succeeds."""
    merged_meta = merge_local_metadata(parent_dir, is_remote=is_remote)
    
    is_series = bool(merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
    is_json_only = bool(not merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
    series_cover_url = merged_meta.get('cover_image_url', '') if is_json_only else ''
    b64_keys_lower = {k.lower(): v for k, v in merged_meta.get('cover_b64_map', {}).items()}
    
    shared_cover = None
    results = []
    
    for row in folder_rows:
        book_id = row['id']
        file_path = row['file_path']
        filename = os.path.basename(file_path)
        series_name = row['series_name']
        file_format = (row['file_format'] or '').lower() if 'file_format' in row.keys() else ''
        is_imgdir = (file_format == 'imgdir') or file_path.lower().endswith('.imgdir')
        imgdir_folder_path = os.path.dirname(file_path) if is_imgdir else None
        
        file_exists = os.path.exists(file_path)
        
        cover_image = None
        filename_lower = filename.lower()
        
        # 1) kavita.yaml Base64 cover - no actual file access needed, remote files supported
        if filename_lower in b64_keys_lower:
            cover_image = extract_cover_from_b64(file_path, b64_keys_lower[filename_lower], force=True, library_id=library_id)
        
        # 2) Reuse already shared cover (if series folder) - no file access needed
        if not cover_image and (is_series or is_json_only) and shared_cover:
            print(f"[Scanner-Covers] Series cover cloned: '{filename}'")
            cover_image = shared_cover
        
        # 3) series.json URL download - no actual file access needed, remote files supported
        if not cover_image and is_json_only and series_cover_url:
            cover_image = download_cover_from_url(file_path, series_cover_url, force=True, library_id=library_id)
        
        # 4) Fallback: first image in archive - requires file access, skip if none -> delegate to Lazy Scanner
        if not cover_image:
            if is_imgdir and imgdir_folder_path and os.path.isdir(imgdir_folder_path):
                cover_image = get_imgdir_cover(imgdir_folder_path, file_path, force=True, library_id=library_id)
            elif not file_exists:
                print(f"[Scanner-Covers] Remote file unreachable -> Delegated to Lazy scanner: '{filename}'")
            else:
                cover_image = get_series_cover_fallback(
                    series_name, parent_dir, force=True, is_remote=is_remote,
                    filename=filename, file_path=file_path, library_id=library_id
                )

        
        # Cache upon first successful shared cover
        if (is_series or is_json_only) and cover_image and not shared_cover:
            shared_cover = cover_image
        
        if cover_image:
            results.append((book_id, cover_image))
    
    return results

