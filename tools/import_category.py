# -*- coding: utf-8 -*-
"""
tools/import_category.py
------------------------------------------------
BookOasis 카테고리(라이브러리) 메타데이터 및 커버 이미지 가져오기 (Import) & 기존 카테고리 병합 (Merge) CLI 도구
(단일 및 다중 물리 디렉토리 경로 Multi-path 완벽 지원)
"""

import os
import sys
import json
import argparse
import zipfile
import shutil
import datetime

# 프로젝트 루트 디렉터리를 sys.path에 추가
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import database
from services.cover_storage_service import get_covers_dir

def get_db_connection(db_type):
    if not database.is_mariadb_mode():
        db_path = database.get_db_path(db_type)
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found at: {db_path}")
    return database.get_connection(db_type)

def parse_target_paths(raw_args):
    result = []
    if not raw_args:
        return result
    if isinstance(raw_args, str):
        raw_args = [raw_args]

    for item in raw_args:
        parts = item.replace('\r', '').replace(';', '\n').replace(',', '\n').split('\n')
        for sub in parts:
            cleaned = sub.strip()
            if cleaned:
                result.append(os.path.abspath(cleaned))
    return result


def get_table_columns(cursor, table_name):
    """SQLite/MariaDB 양쪽에서 동작하는, 실제 DB에 존재하는 테이블 컬럼 목록 조회.
    스키마가 버전마다 조금씩 달라지므로(예: audiobook_tracks.title/created_at은
    MariaDB 스키마에만 존재하고 SQLite 스키마에는 없음), INSERT 문을 하드코딩하지 않고
    이 목록으로 컬럼 존재 여부를 확인해 걸러낸다."""
    if database.is_mariadb_mode():
        cursor.execute(
            "SELECT COLUMN_NAME FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = ?",
            (table_name,),
        )
        rows = cursor.fetchall()
        return {row[0] if not isinstance(row, dict) else row['COLUMN_NAME'] for row in rows}
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row['name'] if isinstance(row, dict) or hasattr(row, 'keys') else row[1] for row in cursor.fetchall()}


def upsert_record(cursor, table, key_columns, values):
    """내부에서 지정한 키를 기준으로 엔진 독립적인 UPDATE/INSERT를 수행합니다."""
    where_clause = " AND ".join(f"`{column}` = ?" for column in key_columns)
    cursor.execute(
        f"SELECT id FROM `{table}` WHERE {where_clause}",
        tuple(values[column] for column in key_columns),
    )
    existing = cursor.fetchone()
    if existing:
        update_columns = [
            column for column in values
            if column not in key_columns and column != 'id'
        ]
        set_clause = ", ".join(f"`{column}` = ?" for column in update_columns)
        cursor.execute(
            f"UPDATE `{table}` SET {set_clause} WHERE id = ?",
            tuple(values[column] for column in update_columns) + (existing['id'],),
        )
        return existing['id']

    insert_columns = [column for column in values if column != 'id']
    column_clause = ", ".join(f"`{column}`" for column in insert_columns)
    placeholders = ", ".join("?" for _ in insert_columns)
    cursor.execute(
        f"INSERT INTO `{table}` ({column_clause}) VALUES ({placeholders})",
        tuple(values[column] for column in insert_columns),
    )
    return cursor.lastrowid


def invalidate_series_summary(cursor, library_id):
    cursor.execute("DELETE FROM series_summary WHERE library_id = ?", (library_id,))
    cursor.execute("SELECT id FROM series_summary_state WHERE id = 1")
    if cursor.fetchone():
        cursor.execute(
            "UPDATE series_summary_state SET is_ready = 0, refreshed_at = NULL WHERE id = 1"
        )
    else:
        cursor.execute(
            "INSERT INTO series_summary_state (id, is_ready, refreshed_at) VALUES (1, 0, NULL)"
        )

def get_all_existing_libraries():
    """모든 DB(General 및 Adult)의 기존 카테고리 목록을 수집합니다."""
    libraries = []
    for db_type in ['general', 'adult', 'audiobook', 'video']:
        try:
            conn = get_db_connection(db_type)
            cur = conn.cursor()
            cur.execute("SELECT id, name, physical_path FROM libraries ORDER BY id ASC")
            rows = cur.fetchall()
            for r in rows:
                libraries.append({
                    'db_type': db_type,
                    'id': r['id'],
                    'name': r['name'],
                    'physical_path': r['physical_path']
                })
            conn.close()
        except Exception:
            pass
    return libraries

def inspect_package(input_path):
    if not os.path.exists(input_path):
        print(f"[!] Error: Package file not found at '{input_path}'")
        sys.exit(1)

    try:
        with zipfile.ZipFile(input_path, 'r') as zipf:
            namelist = zipf.namelist()
            if 'manifest.json' not in namelist or 'metadata.json' not in namelist:
                print("[!] Error: Invalid package format. Missing manifest.json or metadata.json.")
                sys.exit(1)

            manifest = json.loads(zipf.read('manifest.json').decode('utf-8'))
            metadata = json.loads(zipf.read('metadata.json').decode('utf-8'))

            cover_count = sum(1 for m in namelist if m.startswith('covers/') and not m.endswith('/'))
    except Exception as e:
        print(f"[!] Error inspecting package: {e}")
        sys.exit(1)

    lib_info = metadata.get('library', {})
    books_info = metadata.get('books', [])
    audiobooks_info = metadata.get('audiobooks', [])
    audiobook_tracks_info = metadata.get('audiobook_tracks', [])
    audiobook_progress_info = metadata.get('audiobook_progress', [])
    audiobook_track_progress_info = metadata.get('audiobook_track_progress', [])
    videos_info = metadata.get('videos', [])
    video_episodes_info = metadata.get('video_episodes', [])
    video_progress_info = metadata.get('video_progress', [])
    user_progress_info = metadata.get('user_progress', [])
    root_paths = lib_info.get('physical_paths', [])
    orig_root_count = manifest.get('root_paths_count', len(root_paths))
    media_kind = manifest.get('media_kind', 'book')

    print("==========================================================")
    print("📦 [BookOasis Package Inspection Info]")
    print("==========================================================")
    print(f"  • Category Name : {manifest.get('library_name') or lib_info.get('name')}")
    print(f"  • DB Type       : {manifest.get('db_type', 'general')}")
    if media_kind == 'video' or manifest.get('db_type') == 'video':
        print(f"  • Total Video Courses : {manifest.get('videos_count', len(videos_info))} items")
        print(f"  • Total Episodes      : {manifest.get('video_episodes_count', len(video_episodes_info))} items")
        print(f"  • Total Progress      : {manifest.get('video_progress_count', len(video_progress_info))} items")
    elif media_kind == 'audiobook' or manifest.get('db_type') == 'audiobook':
        print(f"  • Total Audiobooks : {manifest.get('audiobooks_count', len(audiobooks_info))} items")
        print(f"  • Total Tracks     : {manifest.get('audiobook_tracks_count', len(audiobook_tracks_info))} items")
        print(f"  • Total Progress   : {manifest.get('audiobook_progress_count', len(audiobook_progress_info))} items")
        print(f"  • Track Progress   : {manifest.get('audiobook_track_progress_count', len(audiobook_track_progress_info))} items")
    else:
        print(f"  • Total Books   : {manifest.get('books_count', len(books_info))} items")
        print(f"  • Total Progress: {manifest.get('user_progress_count', len(user_progress_info))} items")
    print(f"  • Total Covers  : {cover_count} files")
    print(f"  • Original Physical Paths Count : {orig_root_count} entries")
    for idx, rp in enumerate(root_paths):
        print(f"    [{idx}] {rp}")
    print("==========================================================")
    print(f"👉 Import Recommendations:")
    print(f"   1) 신규 카테고리로 가져오기:")
    print(f"      python tools/import_category.py -i \"{input_path}\" -p \"/path/to/target\" -n \"새 이름\"")
    print(f"   2) 기존 카테고리에 병합(Merge)하기:")
    print(f"      python tools/import_category.py -i \"{input_path}\" --merge-to <카테고리ID 또는 이름> -p \"/path/to/target\"")
    print("==========================================================")

    # 기존 DB 카테고리 목록 안내 (병합 참조용)
    existing_libs = get_all_existing_libraries()
    if existing_libs:
        print("\n📂 [Existing DB Categories Available for Merging (--merge-to)]")
        print("----------------------------------------------------------")
        for el in existing_libs:
            paths_short = (el['physical_path'] or '').replace('\n', ' | ')
            print(f"  • [{el['db_type'].upper()}] ID {el['id']:<3} | 이름: '{el['name']}' (경로: {paths_short})")
        print("----------------------------------------------------------")


def import_category(input_path, target_paths_raw, db_type=None, name=None, merge_to=None):
    if not os.path.exists(input_path):
        print(f"[!] Error: Import package not found at '{input_path}'")
        sys.exit(1)

    target_paths = parse_target_paths(target_paths_raw)
    if not target_paths:
        print("[!] Error: At least one target physical path (--target-path / -p) must be specified.")
        sys.exit(1)

    print(f"[*] Reading export package from '{input_path}'...")
    try:
        with zipfile.ZipFile(input_path, 'r') as zipf:
            namelist = zipf.namelist()
            if 'manifest.json' not in namelist or 'metadata.json' not in namelist:
                print("[!] Error: Invalid package format. Missing manifest.json or metadata.json.")
                sys.exit(1)

            manifest = json.loads(zipf.read('manifest.json').decode('utf-8'))
            metadata = json.loads(zipf.read('metadata.json').decode('utf-8'))
    except Exception as e:
        print(f"[!] Error reading zip package: {e}")
        sys.exit(1)

    target_db_type = db_type if db_type else manifest.get('db_type', 'general')
    package_media_kind = manifest.get('media_kind')
    if not package_media_kind:
        package_media_kind = 'audiobook' if manifest.get('db_type') == 'audiobook' else (
            'video' if manifest.get('db_type') == 'video' else 'book'
        )
    expected_media_kind = 'audiobook' if target_db_type == 'audiobook' else (
        'video' if target_db_type == 'video' else 'book'
    )
    if package_media_kind != expected_media_kind:
        print(
            f"[!] Error: Package media type and target DB do not match "
            f"(package={package_media_kind}, target={target_db_type})."
        )
        sys.exit(1)

    lib_info = metadata.get('library', {})
    orig_root_paths = lib_info.get('physical_paths', [])
    orig_root_count = manifest.get('root_paths_count', len(orig_root_paths))

    conn = get_db_connection(target_db_type)
    cursor = conn.cursor()

    is_merge_mode = False
    target_library_id = None
    target_lib_name = None

    # 1. 병합(Merge) 모드 판별 및 기존 카테고리 검색
    if merge_to is not None and str(merge_to).strip():
        is_merge_mode = True
        merge_target_str = str(merge_to).strip()
        
        # ID로 검색 시도
        if merge_target_str.isdigit():
            cursor.execute("SELECT id, name, physical_path FROM libraries WHERE id = ?", (int(merge_target_str),))
            existing_lib = cursor.fetchone()
        else:
            existing_lib = None

        # 이름으로 검색 시도
        if not existing_lib:
            cursor.execute("SELECT id, name, physical_path FROM libraries WHERE name = ?", (merge_target_str,))
            existing_lib = cursor.fetchone()

        if not existing_lib:
            print(f"[!] Error: Target category '{merge_to}' for merging not found in '{target_db_type}' DB.")
            print(f"    Available categories in '{target_db_type}' DB:")
            cursor.execute("SELECT id, name FROM libraries ORDER BY id ASC")
            for row in cursor.fetchall():
                print(f"      - ID {row['id']}: {row['name']}")
            conn.close()
            sys.exit(1)

        target_library_id = existing_lib['id']
        target_lib_name = existing_lib['name']
        print(f"[🔗 MERGE MODE] Merging package into existing category: ID {target_library_id} ('{target_lib_name}')")

        # 기존 카테고리의 physical_path에 신규 target_paths 추가 및 통합 (중복 제거)
        existing_paths = [p.strip() for p in (existing_lib['physical_path'] or '').split('\n') if p.strip()]
        merged_paths = existing_paths.copy()
        for tp in target_paths:
            if tp not in merged_paths:
                merged_paths.append(tp)
        
        updated_physical_path = "\n".join(merged_paths)
        cursor.execute("UPDATE libraries SET physical_path = ? WHERE id = ?", (updated_physical_path, target_library_id))
        conn.commit()
        print(f"[+] Updated library physical paths: {len(existing_paths)} existing -> {len(merged_paths)} merged entries.")

    else:
        # 신규 카테고리 생성 모드 (이름 중복 방지 처리)
        target_lib_name = name if name else metadata.get('library', {}).get('name', 'Imported Library')
        cursor.execute("SELECT id FROM libraries WHERE name = ?", (target_lib_name,))
        existing_lib = cursor.fetchone()
        if existing_lib:
            target_lib_name = f"{target_lib_name} (Imported {datetime.datetime.now().strftime('%H%M%S')})"
            print(f"[!] Library name collision detected. Renamed new category to: '{target_lib_name}'")

        db_physical_path = "\n".join(target_paths)
        cursor.execute("""
            INSERT INTO libraries (
                name, physical_path, cron_schedule, scan_status, is_remote,
                vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover,
                group_id, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            target_lib_name,
            db_physical_path,
            lib_info.get('cron_schedule'),
            'ready',
            lib_info.get('is_remote', 0),
            lib_info.get('vfs_refresh_before_scan', 0),
            lib_info.get('rclone_rc_url'),
            lib_info.get('icon', 'fa-book'),
            lib_info.get('color', '#94a3b8'),
            lib_info.get('hide_cover', 0),
            lib_info.get('group_id'),
            lib_info.get('sort_order', 0)
        ))
        target_library_id = cursor.lastrowid
        conn.commit()
        print(f"[+] Created new library in DB (ID: {target_library_id}, Name: '{target_lib_name}')")

    print(f"[+] Package Import Configuration:")
    print(f"    - Mode: {'MERGE INTO EXISTING CATEGORY' if is_merge_mode else 'CREATE NEW CATEGORY'}")
    print(f"    - Target Category: ID {target_library_id} ('{target_lib_name}')")
    print(f"    - Target DB Type: {target_db_type}")
    print(f"    - Target Physical Paths ({len(target_paths)} provided):")
    for idx, tp in enumerate(target_paths):
        print(f"      [{idx}] {tp}")

    if orig_root_count > len(target_paths):
        print(f"[!] Warning: Package has {orig_root_count} original root paths, but only {len(target_paths)} target paths provided.")
        print(f"    Unmatched index items will fall back to target path [0]: {target_paths[0]}")

    # 2. 대상 디렉터리 존재 검사 및 자동 생성
    for tp in target_paths:
        if not os.path.exists(tp):
            try:
                os.makedirs(tp, exist_ok=True)
                print(f"[+] Created target directory: {tp}")
            except Exception as e:
                print(f"[!] Error creating target directory '{tp}': {e}")

    # 3. 커버 이미지 복원 (target_library_id 폴더 하위로 복원)
    covers_dir = get_covers_dir()
    lib_covers_dir = os.path.join(covers_dir, str(target_library_id))
    os.makedirs(lib_covers_dir, exist_ok=True)

    extracted_covers = 0
    with zipfile.ZipFile(input_path, 'r') as zipf:
        for member in zipf.namelist():
            if member.startswith('covers/') and not member.endswith('/'):
                filename = os.path.basename(member)
                if filename:
                    target_cover_path = os.path.join(lib_covers_dir, filename)
                    with zipf.open(member) as source, open(target_cover_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    extracted_covers += 1

    print(f"[+] Extracted {extracted_covers} cover images to '{lib_covers_dir}'.")

    # 4. 도서(books) 및 offset 데이터 복원 (root_index 기준 매핑)
    books_list = metadata.get('books', [])
    offsets_dict = metadata.get('offsets', {})
    audiobooks_list = metadata.get('audiobooks', [])
    audiobook_tracks_list = metadata.get('audiobook_tracks', [])
    audiobook_progress_list = metadata.get('audiobook_progress', [])
    audiobook_track_progress_list = metadata.get('audiobook_track_progress', [])
    videos_list = metadata.get('videos', [])
    video_episodes_list = metadata.get('video_episodes', [])
    video_progress_list = metadata.get('video_progress', [])
    video_episode_progress_list = metadata.get('video_episode_progress', [])
    user_progress_list = metadata.get('user_progress', [])
    user_favorites_list = metadata.get('user_favorites', [])

    imported_books_count = 0
    skipped_duplicate_books_count = 0
    imported_offsets_count = 0
    imported_audiobooks_count = 0
    imported_audiobook_tracks_count = 0
    imported_audiobook_progress_count = 0
    imported_audiobook_track_progress_count = 0
    imported_videos_count = 0
    imported_video_episodes_count = 0
    imported_video_progress_count = 0
    imported_video_episode_progress_count = 0
    skipped_duplicate_videos_count = 0
    skipped_duplicate_episodes_count = 0
    imported_user_progress_count = 0
    imported_user_favorites_count = 0
    skipped_duplicate_audiobooks_count = 0
    skipped_duplicate_tracks_count = 0

    if target_db_type == 'video':
        video_index_to_new_id = {}
        video_index_to_target_root = {}
        episode_lookup = {}

        for idx, v in enumerate(videos_list):
            rel_folder = v.get('relative_folder_path', '')
            root_idx = int(v.get('root_index', 0) or 0)
            if root_idx < len(target_paths):
                selected_target_root = target_paths[root_idx]
            else:
                selected_target_root = target_paths[0]
            video_index_to_target_root[idx] = selected_target_root

            clean_rel = rel_folder.replace('/', os.sep).replace('\\', os.sep)
            new_folder_path = os.path.normpath(os.path.join(selected_target_root, clean_rel)) if clean_rel else selected_target_root

            poster = v.get('poster', '')
            if poster and not str(poster).startswith(('http://', 'https://')):
                filename = os.path.basename(poster)
                mapped = os.path.join(lib_covers_dir, filename)
                poster = mapped if os.path.exists(mapped) else poster

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("SELECT id FROM videos WHERE folder_path = ?", (new_folder_path,))
            dup_v = cursor.fetchone()
            if dup_v:
                skipped_duplicate_videos_count += 1
                video_index_to_new_id[idx] = int(dup_v['id'])
                continue

            try:
                cursor.execute("""
                    INSERT INTO videos (
                        library_id, title, sort_title, web_id, genres, poster, backdrop,
                        premiered, description, folder_name, folder_path, total_duration, total_episodes,
                        is_favorite, created_at, updated_at, is_deleted, deleted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_library_id,
                    v.get('title', 'Unknown Video Course'),
                    v.get('sort_title'),
                    v.get('web_id'),
                    v.get('genres'),
                    poster,
                    v.get('backdrop'),
                    v.get('premiered'),
                    v.get('description'),
                    v.get('folder_name') or os.path.basename(new_folder_path),
                    new_folder_path,
                    v.get('total_duration', 0.0),
                    v.get('total_episodes', 0),
                    v.get('is_favorite', 0),
                    v.get('created_at') or now_str,
                    v.get('updated_at') or now_str,
                    v.get('is_deleted', 0),
                    v.get('deleted_at')
                ))
                new_video_id = cursor.lastrowid
                video_index_to_new_id[idx] = int(new_video_id)
                imported_videos_count += 1
            except Exception as v_err:
                print(f"[!] Error inserting video course '{v.get('title')}': {v_err}")
                continue

        # video_episodes 스키마도 audiobook_tracks와 마찬가지로 백엔드마다 컬럼 구성이
        # 조금씩 다를 수 있으므로(예: needs_transcode/subtitle_path 자동보강 시점 차이),
        # 실제 대상 테이블에 있는 컬럼만 골라 동적으로 INSERT 문을 구성한다.
        available_episode_columns = get_table_columns(cursor, 'video_episodes')

        for ep in video_episodes_list:
            v_idx = int(ep.get('video_export_index', -1))
            if v_idx not in video_index_to_new_id:
                continue
            new_video_id = video_index_to_new_id[v_idx]

            root_idx = int(ep.get('root_index', 0) or 0)
            if root_idx < len(target_paths):
                selected_target_root = target_paths[root_idx]
            else:
                selected_target_root = video_index_to_target_root.get(v_idx, target_paths[0])

            rel_path = str(ep.get('relative_path', '') or '')
            clean_rel = rel_path.replace('/', os.sep).replace('\\', os.sep)
            new_episode_path = os.path.normpath(os.path.join(selected_target_root, clean_rel)) if clean_rel else ''

            if new_episode_path:
                cursor.execute("SELECT id FROM video_episodes WHERE file_path = ?", (new_episode_path,))
                dup_ep = cursor.fetchone()
                if dup_ep:
                    skipped_duplicate_episodes_count += 1
                    episode_number = int(ep.get('episode_number') or 0)
                    if episode_number > 0:
                        episode_lookup[(new_video_id, episode_number)] = int(dup_ep['id'])
                    continue

            try:
                episode_values = {
                    'video_id': new_video_id,
                    'episode_number': ep.get('episode_number', 0),
                    'episode_code': ep.get('episode_code'),
                    'title': ep.get('title'),
                    'filename': ep.get('filename', ''),
                    'file_path': new_episode_path,
                    'file_mtime': ep.get('file_mtime', 0.0),
                    'file_size': ep.get('file_size', 0),
                    'duration': ep.get('duration', 0.0),
                    'width': ep.get('width', 0),
                    'height': ep.get('height', 0),
                    'premiered': ep.get('premiered'),
                    'format': ep.get('format', 'mp4'),
                    'needs_transcode': ep.get('needs_transcode', 0),
                    'subtitle_path': ep.get('subtitle_path'),
                }
                episode_values = {k: v for k, v in episode_values.items() if k in available_episode_columns}
                columns_clause = ", ".join(f"`{c}`" for c in episode_values)
                placeholders = ", ".join("?" for _ in episode_values)
                cursor.execute(
                    f"INSERT INTO video_episodes ({columns_clause}) VALUES ({placeholders})",
                    tuple(episode_values.values()),
                )
                new_episode_id = int(cursor.lastrowid)
                episode_number = int(ep.get('episode_number') or 0)
                if episode_number > 0:
                    episode_lookup[(new_video_id, episode_number)] = new_episode_id
                imported_video_episodes_count += 1
            except Exception as ep_err:
                print(f"[!] Error inserting video episode '{ep.get('filename', '')}': {ep_err}")

        for vp in video_progress_list:
            v_idx = int(vp.get('video_export_index', -1))
            if v_idx not in video_index_to_new_id:
                continue
            new_video_id = video_index_to_new_id[v_idx]
            episode_num = int(vp.get('current_episode_number') or 0)
            mapped_episode_id = episode_lookup.get((new_video_id, episode_num)) if episode_num > 0 else None

            try:
                upsert_record(cursor, 'video_progress', ('video_id', 'user_id'), {
                    'video_id': new_video_id,
                    'user_id': vp.get('user_id', 1),
                    'current_episode_id': mapped_episode_id,
                    'current_time': vp.get('current_time', 0.0),
                    'total_progress_pct': vp.get('total_progress_pct', 0.0),
                    'playback_rate': vp.get('playback_rate', 1.0),
                    'is_completed': vp.get('is_completed', 0),
                    'last_watched_at': vp.get('last_watched_at') or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                imported_video_progress_count += 1
            except Exception as vp_err:
                print(f"[!] Error inserting video progress row: {vp_err}")

        for progress in video_episode_progress_list:
            v_idx = int(progress.get('video_export_index', -1))
            if v_idx not in video_index_to_new_id:
                continue
            new_video_id = video_index_to_new_id[v_idx]
            episode_number = int(progress.get('episode_number') or 0)
            mapped_episode_id = episode_lookup.get((new_video_id, episode_number))
            if not mapped_episode_id:
                continue
            try:
                upsert_record(
                    cursor,
                    'video_episode_progress',
                    ('video_id', 'episode_id', 'user_id'),
                    {
                        'video_id': new_video_id,
                        'episode_id': mapped_episode_id,
                        'user_id': progress.get('user_id', 1),
                        'current_time': progress.get('current_time', 0.0),
                        'progress_pct': progress.get('progress_pct', 0.0),
                        'is_completed': progress.get('is_completed', 0),
                        'updated_at': progress.get('updated_at') or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                )
                imported_video_episode_progress_count += 1
            except Exception as progress_error:
                print(f"[!] Error inserting video episode progress row: {progress_error}")
    elif target_db_type == 'audiobook':
        audiobook_index_to_new_id = {}
        audiobook_index_to_target_root = {}
        track_lookup = {}

        for idx, ab in enumerate(audiobooks_list):
            rel_folder = ab.get('relative_folder_path', '')
            root_idx = int(ab.get('root_index', 0) or 0)
            if root_idx < len(target_paths):
                selected_target_root = target_paths[root_idx]
            else:
                selected_target_root = target_paths[0]
            audiobook_index_to_target_root[idx] = selected_target_root

            clean_rel = rel_folder.replace('/', os.sep).replace('\\', os.sep)
            new_folder_path = os.path.normpath(os.path.join(selected_target_root, clean_rel)) if clean_rel else selected_target_root

            poster = ab.get('poster', '')
            if poster and not str(poster).startswith(('http://', 'https://')):
                filename = os.path.basename(poster)
                mapped = os.path.join(lib_covers_dir, filename)
                poster = mapped if os.path.exists(mapped) else poster

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("SELECT id FROM audiobooks WHERE folder_path = ?", (new_folder_path,))
            dup_ab = cursor.fetchone()
            if dup_ab:
                skipped_duplicate_audiobooks_count += 1
                audiobook_index_to_new_id[idx] = int(dup_ab['id'])
                continue

            try:
                cursor.execute("""
                    INSERT INTO audiobooks (
                        library_id, title, sort_title, web_id, author, publisher, code, poster,
                        premiered, ratings, author_intro, description,
                        folder_name, folder_path, total_duration, total_tracks, file_type,
                        is_favorite, created_at, updated_at, is_deleted, deleted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_library_id,
                    ab.get('title', 'Unknown Audiobook'),
                    ab.get('sort_title'),
                    ab.get('web_id'),
                    ab.get('author'),
                    ab.get('publisher'),
                    ab.get('code'),
                    poster,
                    ab.get('premiered'),
                    ab.get('ratings', 0.0),
                    ab.get('author_intro'),
                    ab.get('description'),
                    ab.get('folder_name') or os.path.basename(new_folder_path),
                    new_folder_path,
                    ab.get('total_duration', 0.0),
                    ab.get('total_tracks', 0),
                    ab.get('file_type', 'multi'),
                    ab.get('is_favorite', 0),
                    ab.get('created_at') or now_str,
                    ab.get('updated_at') or now_str,
                    ab.get('is_deleted', 0),
                    ab.get('deleted_at')
                ))
                new_ab_id = cursor.lastrowid
                audiobook_index_to_new_id[idx] = int(new_ab_id)
                imported_audiobooks_count += 1
            except Exception as ab_err:
                print(f"[!] Error inserting audiobook '{ab.get('title')}': {ab_err}")
                continue

        # audiobook_tracks 스키마는 백엔드마다 다르다(예: title/created_at 컬럼은
        # MariaDB에만 있고 SQLite에는 없음). 하드코딩된 컬럼 목록으로 INSERT하면
        # 컬럼이 없는 백엔드에서 전체 가져오기가 실패하므로, 실제 대상 테이블에 있는
        # 컬럼만 골라 동적으로 INSERT 문을 구성한다.
        available_track_columns = get_table_columns(cursor, 'audiobook_tracks')

        for tr in audiobook_tracks_list:
            ab_idx = int(tr.get('audiobook_export_index', -1))
            if ab_idx not in audiobook_index_to_new_id:
                continue
            new_ab_id = audiobook_index_to_new_id[ab_idx]

            root_idx = int(tr.get('root_index', 0) or 0)
            if root_idx < len(target_paths):
                selected_target_root = target_paths[root_idx]
            else:
                selected_target_root = audiobook_index_to_target_root.get(ab_idx, target_paths[0])

            rel_path = str(tr.get('relative_path', '') or '')
            clean_rel = rel_path.replace('/', os.sep).replace('\\', os.sep)
            new_track_path = os.path.normpath(os.path.join(selected_target_root, clean_rel)) if clean_rel else ''

            if new_track_path:
                cursor.execute("SELECT id FROM audiobook_tracks WHERE file_path = ?", (new_track_path,))
                dup_tr = cursor.fetchone()
                if dup_tr:
                    skipped_duplicate_tracks_count += 1
                    track_number = int(tr.get('track_number') or 0)
                    if track_number > 0:
                        track_lookup[(new_ab_id, track_number)] = int(dup_tr['id'])
                    continue

            try:
                track_values = {
                    'audiobook_id': new_ab_id,
                    'track_number': tr.get('track_number', 0),
                    'track_code': tr.get('track_code'),
                    'title': tr.get('title'),
                    'filename': tr.get('filename', ''),
                    'file_path': new_track_path,
                    'file_mtime': tr.get('file_mtime', 0.0),
                    'file_size': tr.get('file_size', 0),
                    'duration': tr.get('duration', 0.0),
                    'format': tr.get('format', 'mp3'),
                    'created_at': tr.get('created_at') or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                track_values = {k: v for k, v in track_values.items() if k in available_track_columns}
                columns_clause = ", ".join(f"`{c}`" for c in track_values)
                placeholders = ", ".join("?" for _ in track_values)
                cursor.execute(
                    f"INSERT INTO audiobook_tracks ({columns_clause}) VALUES ({placeholders})",
                    tuple(track_values.values()),
                )
                new_track_id = int(cursor.lastrowid)
                track_number = int(tr.get('track_number') or 0)
                if track_number > 0:
                    track_lookup[(new_ab_id, track_number)] = new_track_id
                imported_audiobook_tracks_count += 1
            except Exception as tr_err:
                print(f"[!] Error inserting audiobook track '{tr.get('filename', '')}': {tr_err}")

        for pr in audiobook_progress_list:
            ab_idx = int(pr.get('audiobook_export_index', -1))
            if ab_idx not in audiobook_index_to_new_id:
                continue
            new_ab_id = audiobook_index_to_new_id[ab_idx]
            track_num = int(pr.get('current_track_number') or 0)
            mapped_track_id = track_lookup.get((new_ab_id, track_num)) if track_num > 0 else None

            try:
                upsert_record(cursor, 'audiobook_progress', ('audiobook_id', 'user_id'), {
                    'audiobook_id': new_ab_id,
                    'user_id': pr.get('user_id', 1),
                    'current_track_id': mapped_track_id,
                    'current_time': pr.get('current_time', 0.0),
                    'total_progress_pct': pr.get('total_progress_pct', 0.0),
                    'playback_rate': pr.get('playback_rate', 1.0),
                    'is_completed': pr.get('is_completed', 0),
                    'last_listened_at': pr.get('last_listened_at') or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                imported_audiobook_progress_count += 1
            except Exception as pr_err:
                print(f"[!] Error inserting audiobook progress row: {pr_err}")

        for progress in audiobook_track_progress_list:
            ab_idx = int(progress.get('audiobook_export_index', -1))
            if ab_idx not in audiobook_index_to_new_id:
                continue
            new_ab_id = audiobook_index_to_new_id[ab_idx]
            track_number = int(progress.get('track_number') or 0)
            mapped_track_id = track_lookup.get((new_ab_id, track_number))
            if not mapped_track_id:
                continue
            try:
                upsert_record(
                    cursor,
                    'audiobook_track_progress',
                    ('audiobook_id', 'track_id', 'user_id'),
                    {
                        'audiobook_id': new_ab_id,
                        'track_id': mapped_track_id,
                        'user_id': progress.get('user_id', 1),
                        'current_time': progress.get('current_time', 0.0),
                        'progress_pct': progress.get('progress_pct', 0.0),
                        'is_completed': progress.get('is_completed', 0),
                        'updated_at': progress.get('updated_at') or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                )
                imported_audiobook_track_progress_count += 1
            except Exception as progress_error:
                print(f"[!] Error inserting audiobook track progress row: {progress_error}")
    else:
        book_index_to_new_id = {}
        for idx, b in enumerate(books_list):
            rel_path = b.get('relative_path', '')
            if not rel_path:
                continue

            root_idx = int(b.get('root_index', 0) or 0)
            if root_idx < len(target_paths):
                selected_target_root = target_paths[root_idx]
            else:
                selected_target_root = target_paths[0]

            clean_rel = rel_path.replace('/', os.sep).replace('\\', os.sep)
            new_file_path = os.path.normpath(os.path.join(selected_target_root, clean_rel))

            cover_img = b.get('cover_image', '')
            if cover_img:
                filename = os.path.basename(cover_img)
                cover_img = f"{target_library_id}/{filename}"

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("SELECT id FROM books WHERE file_path = ?", (new_file_path,))
            dup_book = cursor.fetchone()
            if dup_book:
                skipped_duplicate_books_count += 1
                book_index_to_new_id[idx] = int(dup_book['id'])
                print(f"[!] Skipping duplicate file path: '{new_file_path}' (Existing Book ID: {dup_book['id']})")
                continue

            try:
                cursor.execute("""
                    INSERT INTO books (
                        library_id, title, series_name, author, isbn, file_path, file_format,
                        total_pages, has_offsets, cover_image, publisher, link, score,
                        release_date, summary, genre, tags, is_favorite, cover_updated_at,
                        created_at, is_deleted, deleted_at, metadata_locked, series_alias,
                        title_alias, file_mtime, file_size
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_library_id,
                    b.get('title', 'Unknown Title'),
                    b.get('series_name'),
                    b.get('author'),
                    b.get('isbn'),
                    new_file_path,
                    b.get('file_format', 'zip'),
                    b.get('total_pages', 0),
                    b.get('has_offsets', 0),
                    cover_img,
                    b.get('publisher'),
                    b.get('link'),
                    b.get('score'),
                    b.get('release_date'),
                    b.get('summary'),
                    b.get('genre'),
                    b.get('tags'),
                    b.get('is_favorite', 0),
                    b.get('cover_updated_at', now_str),
                    b.get('created_at') or now_str,
                    b.get('is_deleted', 0),
                    b.get('deleted_at'),
                    b.get('metadata_locked', 0),
                    b.get('series_alias'),
                    b.get('title_alias'),
                    b.get('file_mtime', 0.0),
                    b.get('file_size', 0)
                ))
                new_book_id = cursor.lastrowid
                book_index_to_new_id[idx] = int(new_book_id)
                imported_books_count += 1

                idx_key = str(idx)
                if idx_key in offsets_dict:
                    for off in offsets_dict[idx_key]:
                        cursor.execute("""
                            INSERT INTO book_offsets (
                                book_id, page_idx, filename, local_header_offset,
                                compress_size, file_size, compress_type, data_offset
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            new_book_id,
                            off.get('page_idx'),
                            off.get('filename'),
                            off.get('local_header_offset'),
                            off.get('compress_size'),
                            off.get('file_size'),
                            off.get('compress_type'),
                            off.get('data_offset')
                        ))
                        imported_offsets_count += 1

            except Exception as b_err:
                print(f"[!] Error inserting book '{b.get('title')}': {b_err}")
                continue

        for progress in user_progress_list:
            book_idx = int(progress.get('book_export_index', -1))
            if book_idx not in book_index_to_new_id:
                continue
            try:
                values = {
                    column: value
                    for column, value in progress.items()
                    if column not in ('id', 'book_export_index', 'book_id')
                }
                values['book_id'] = book_index_to_new_id[book_idx]
                values.setdefault('user_id', 1)
                upsert_record(cursor, 'user_progress', ('book_id', 'user_id'), values)
                imported_user_progress_count += 1
            except Exception as progress_error:
                print(f"[!] Error inserting book progress row: {progress_error}")

        for favorite in user_favorites_list:
            book_idx = int(favorite.get('book_export_index', -1))
            if book_idx not in book_index_to_new_id:
                continue
            try:
                upsert_record(cursor, 'user_favorites', ('user_id', 'book_id'), {
                    'user_id': favorite.get('user_id', 1),
                    'book_id': book_index_to_new_id[book_idx],
                    'created_at': favorite.get('created_at') or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                imported_user_favorites_count += 1
            except Exception as favorite_error:
                print(f"[!] Error inserting favorite row: {favorite_error}")

        invalidate_series_summary(cursor, target_library_id)

    conn.commit()
    conn.close()

    print("==========================================================")
    print(f"✨ Category Import / Merge Successfully Completed!")
    print(f"   - Import Mode: {'Merged into Category ID ' + str(target_library_id) if is_merge_mode else 'Created New Category ID ' + str(target_library_id)}")
    print(f"   - Library Name: {target_lib_name}")
    print(f"   - Target Physical Paths ({len(target_paths)} entries):")
    for tp in target_paths:
        print(f"     * {tp}")
    if target_db_type == 'video':
        print(f"   - Imported Video Courses: {imported_videos_count} / {len(videos_list)} (Skipped Duplicates: {skipped_duplicate_videos_count})")
        print(f"   - Imported Episodes: {imported_video_episodes_count} / {len(video_episodes_list)} (Skipped Duplicates: {skipped_duplicate_episodes_count})")
        print(f"   - Imported Video Progress: {imported_video_progress_count} / {len(video_progress_list)}")
        print(f"   - Imported Episode Progress: {imported_video_episode_progress_count} / {len(video_episode_progress_list)}")
    elif target_db_type == 'audiobook':
        print(f"   - Imported Audiobooks: {imported_audiobooks_count} / {len(audiobooks_list)} (Skipped Duplicates: {skipped_duplicate_audiobooks_count})")
        print(f"   - Imported Audiobook Tracks: {imported_audiobook_tracks_count} / {len(audiobook_tracks_list)} (Skipped Duplicates: {skipped_duplicate_tracks_count})")
        print(f"   - Imported Audiobook Progress: {imported_audiobook_progress_count} / {len(audiobook_progress_list)}")
        print(f"   - Imported Track Progress: {imported_audiobook_track_progress_count} / {len(audiobook_track_progress_list)}")
    else:
        print(f"   - Imported Books: {imported_books_count} / {len(books_list)} (Skipped Duplicates: {skipped_duplicate_books_count})")
        print(f"   - Imported Book Offsets: {imported_offsets_count} items")
        print(f"   - Imported Book Progress: {imported_user_progress_count} / {len(user_progress_list)}")
        print(f"   - Imported Favorites: {imported_user_favorites_count} / {len(user_favorites_list)}")
    print(f"   - Restored Covers: {extracted_covers} files")
    print("==========================================================")


def main():
    parser = argparse.ArgumentParser(
        description="BookOasis Category Import & Merge CLI Tool (Multi-path & Docker Supported)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시 (Usage Examples):

1. 패키지 내용 및 기존 DB 카테고리 미리보기 검사 (Inspect):
   python tools/import_category.py -i 백업파일.oasis.zip --info

2. 신규 카테고리로 가져오기 (Import as New Category):
   python tools/import_category.py -i 백업파일.oasis.zip -p "/volume1/mnt/만화" -n "이관된 만화함"

3. 기존 카테고리에 병합(Merge)하기 (Category Merge into Existing):
   # 카테고리 ID로 병합
   python tools/import_category.py -i 백업파일.oasis.zip --merge-to 15 -p "/volume1/mnt/만화B"

   # 카테고리 이름으로 병합
   python tools/import_category.py -i 백업파일.oasis.zip --merge-to "판타지 소설" -p "/volume1/mnt/소설B"

4. 도커(Docker) 환경 실행 예시:
   docker exec -it bookoasis python tools/import_category.py -i /app/covers/백업.oasis.zip --merge-to 15 -p "/volume1/mnt/만화B"
"""
    )
    parser.add_argument("-i", "--input", type=str, required=True, help="Path to input .oasis.zip package")
    parser.add_argument("-p", "--target-path", action="append", default=None, help="New target physical path(s). Can be specified multiple times (-p path1 -p path2) or comma-separated")
    parser.add_argument("-d", "--db", choices=['general', 'adult', 'audiobook', 'video'], default=None, help="Target DB type (default: from package manifest)")
    parser.add_argument("-n", "--name", type=str, default=None, help="New category name when creating new category")
    parser.add_argument("-m", "--merge-to", type=str, default=None, help="Merge package into existing category (by Category ID or Category Name) instead of creating a new category")
    parser.add_argument("--info", "--inspect", action="store_true", help="Inspect package metadata, root path info, and list existing DB categories for merging")

    args = parser.parse_args()

    if args.info:
        inspect_package(args.input)
        return

    if not args.target_path:
        print("[!] Error: At least one target physical path (--target-path / -p) is required when importing.")
        print(f"    (Tip: Run 'python {sys.argv[0]} -i \"{args.input}\" --info' to inspect package & DB requirements)")
        sys.exit(1)

    import_category(input_path=args.input, target_paths_raw=args.target_path, db_type=args.db, name=args.name, merge_to=args.merge_to)


if __name__ == '__main__':
    main()
