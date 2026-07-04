# -*- coding: utf-8 -*-
import os
import sys

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import gc
from tools.scanner.parser import parse_info_xml, parse_kavita_yaml, parse_series_json, parse_comicinfo_from_cbz, is_consonant_folder
from tools.scanner.cover import get_series_cover_fallback, extract_cover_from_b64, download_cover_from_url
from tools.scanner.offset import collect_zip_offsets_data

SUPPORTED_FORMATS = ('.zip', '.cbz', '.epub', '.pdf', '.txt')

def process_folder_task(root, files, force, db_meta_full, db_offsets_cached, db_folder_mtimes, is_remote=False, library_id=None):
    """Independent I/O scan task per folder (DB independent, pure FS/I/O scaling)"""
    print(f"[Scanner-DEBUG-Task] 📂 entering process_folder_task - folder: '{root}'")
    
    media_files = [f for f in files if f.lower().endswith(SUPPORTED_FORMATS)]
    if not media_files:
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

    # 2. Early skip if fully cached and no metadata file exists (non-force scan)
    if not force:
        all_cached = True
        for filename in media_files:
            full_path = os.path.join(root, filename)
            if full_path not in db_meta_full:
                all_cached = False
                break
                
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in ('.zip', '.cbz') and not is_remote:
                if full_path not in db_offsets_cached:
                    all_cached = False
                    break
        if all_cached:
            if not has_yaml and not has_xml:
                print(f"[Scanner-DEBUG-Task] ⚡ [Ultra-fast skip] All files cached and metadata irrelevant - folder: '{root}'")
                return None
            else:
                if dir_mtime is not None:
                    cached_mtimes = db_folder_mtimes.get(root)
                    if cached_mtimes:
                        c_dir_mtime, c_meta_mtime = cached_mtimes
                        # 부동소수점 오차 방지를 위해 정수로 변환하여 비교 (1초 단위 정밀도)
                        if int(c_dir_mtime) == int(dir_mtime) and int(c_meta_mtime) == int(meta_mtime):
                            print(f"[Scanner-DEBUG-Task] ⚡ [Ultra-fast skip] All files cached and metadata mtime unchanged - folder: '{root}'")
                            return None
                        else:
                            print(f"[Scanner-DEBUG-Task] ⚠️ [Ultra-fast skip failed] mtime changed (dir: {int(c_dir_mtime)}->{int(dir_mtime)}, meta: {int(c_meta_mtime)}->{int(meta_mtime)}) - folder: '{root}'")

    path_parts = os.path.normpath(root).split(os.sep)
    series_name = ""
    for i in range(len(path_parts) - 1):
        if is_consonant_folder(path_parts[i]):
            series_name = path_parts[i+1]
            break
    if not series_name and len(path_parts) > 0:
        series_name = path_parts[-1]

    if series_name:
        import re
        series_name = re.sub(r'^\[(?:단행|연재|소설|만화|웹툰|일반)\]\s*', '', series_name).strip()

    print(f"[Scanner-DEBUG-Task]   - Metadata YAML/XML/JSON load started")
    yaml_meta = parse_kavita_yaml(root, files=files, is_remote=is_remote)
    xml_meta = parse_info_xml(root, files=files, is_remote=is_remote)
    json_meta = parse_series_json(root, files=files, is_remote=is_remote)
    print(f"[Scanner-DEBUG-Task]   - Metadata load completed")

    merged_meta = {
        'author': xml_meta['author'] or yaml_meta['author'] or json_meta['author'] or '',
        'publisher': xml_meta['publisher'] or yaml_meta['publisher'] or '',
        'summary': xml_meta['summary'] or yaml_meta['summary'] or json_meta['summary'] or '',
        'link': yaml_meta['link'] or '',
        'score': yaml_meta['score'] or 0,
        'release_date': xml_meta['release_date'] or '',
        'genre': xml_meta.get('genre', '') or yaml_meta.get('genre', '') or '',
        'tags': xml_meta.get('tags', '') or yaml_meta.get('tags', '') or '',
        'cover_b64_map': yaml_meta['cover_b64_map'] or {}
    }

    meta_has_data = bool(
        merged_meta['author'] or merged_meta['publisher'] or
        merged_meta['summary'] or merged_meta['release_date'] or
        merged_meta['cover_b64_map']
    )

    is_series_folder = bool(yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
    is_json_only_webtoon = bool(not yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
    series_cover_url = json_meta.get('cover_image_url', '') if is_json_only_webtoon else ''
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

        results.append({
            'full_path': full_path,
            'filename': filename,
            'file_format': file_format,
            'series_name': series_name,
            'cover_image': cover_image,
            'offsets_data': offsets_data,
            'skip': skip,
            'offset_only': offset_only,  # Whether it's offset-only fast path
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
    yaml_meta = parse_kavita_yaml(parent_dir, is_remote=is_remote)
    json_meta = parse_series_json(parent_dir, is_remote=is_remote)
    
    is_series = bool(yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
    is_json_only = bool(not yaml_meta.get('has_yaml') and json_meta.get('is_webtoon'))
    series_cover_url = json_meta.get('cover_image_url', '') if is_json_only else ''
    b64_keys_lower = {k.lower(): v for k, v in yaml_meta.get('cover_b64_map', {}).items()}
    
    shared_cover = None
    results = []
    
    for row in folder_rows:
        book_id = row['id']
        file_path = row['file_path']
        filename = os.path.basename(file_path)
        series_name = row['series_name']
        
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
            if not file_exists:
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

