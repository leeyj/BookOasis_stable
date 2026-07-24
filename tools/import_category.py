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
import sqlite3
import zipfile
import shutil
import datetime

# 프로젝트 루트 디렉터리를 sys.path에 추가
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import database

def get_db_connection(db_type):
    db_path = database.DB_ADULT_PATH if db_type == 'adult' else database.DB_GENERAL_PATH
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

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

def get_all_existing_libraries():
    """모든 DB(General 및 Adult)의 기존 카테고리 목록을 수집합니다."""
    libraries = []
    for db_type in ['general', 'adult']:
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
    root_paths = lib_info.get('physical_paths', [])
    orig_root_count = manifest.get('root_paths_count', len(root_paths))

    print("==========================================================")
    print("📦 [BookOasis Package Inspection Info]")
    print("==========================================================")
    print(f"  • Category Name : {manifest.get('library_name') or lib_info.get('name')}")
    print(f"  • DB Type       : {manifest.get('db_type', 'general')}")
    print(f"  • Total Books   : {manifest.get('total_books', len(books_info))} items")
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
            INSERT INTO libraries (name, physical_path, cron_schedule, icon, color, hide_cover)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            target_lib_name,
            db_physical_path,
            lib_info.get('cron_schedule'),
            lib_info.get('icon', 'fa-book'),
            lib_info.get('color', '#94a3b8'),
            lib_info.get('hide_cover', 0)
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
    covers_dir = os.path.join(BASE_DIR, 'covers')
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

    imported_books_count = 0
    skipped_duplicate_books_count = 0
    imported_offsets_count = 0

    for idx, b in enumerate(books_list):
        rel_path = b.get('relative_path', '')
        if not rel_path:
            continue

        root_idx = b.get('root_index', 0)
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

        # 만약 동일 file_path가 이미 DB에 존재하는지 사전 검사
        cursor.execute("SELECT id FROM books WHERE file_path = ?", (new_file_path,))
        dup_book = cursor.fetchone()
        if dup_book:
            skipped_duplicate_books_count += 1
            print(f"[!] Skipping duplicate file path: '{new_file_path}' (Existing Book ID: {dup_book['id']})")
            continue

        try:
            cursor.execute("""
                INSERT INTO books (
                    library_id, title, series_name, author, isbn, file_path, file_format,
                    total_pages, has_offsets, cover_image, publisher, link, score,
                    release_date, summary, genre, tags, is_favorite, cover_updated_at,
                    created_at, metadata_locked, file_mtime, file_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                now_str,
                b.get('metadata_locked', 0),
                b.get('file_mtime', 0.0),
                b.get('file_size', 0)
            ))
            new_book_id = cursor.lastrowid
            imported_books_count += 1

            # Offset 데이터 복원
            idx_key = str(idx)
            if idx_key in offsets_dict:
                for off in offsets_dict[idx_key]:
                    cursor.execute("""
                        INSERT INTO book_offsets (
                            book_id, page_idx, filename, local_header_offset,
                            compress_size, file_size, compress_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        new_book_id,
                        off.get('page_idx'),
                        off.get('filename'),
                        off.get('local_header_offset'),
                        off.get('compress_size'),
                        off.get('file_size'),
                        off.get('compress_type')
                    ))
                    imported_offsets_count += 1

        except sqlite3.IntegrityError:
            skipped_duplicate_books_count += 1
            print(f"[!] Warning: Skipping duplicate book file: {new_file_path}")
            continue
        except Exception as b_err:
            print(f"[!] Error inserting book '{b.get('title')}': {b_err}")
            continue

    conn.commit()
    conn.close()

    print("==========================================================")
    print(f"✨ Category Import / Merge Successfully Completed!")
    print(f"   - Import Mode: {'Merged into Category ID ' + str(target_library_id) if is_merge_mode else 'Created New Category ID ' + str(target_library_id)}")
    print(f"   - Library Name: {target_lib_name}")
    print(f"   - Target Physical Paths ({len(target_paths)} entries):")
    for tp in target_paths:
        print(f"     * {tp}")
    print(f"   - Imported Books: {imported_books_count} / {len(books_list)} (Skipped Duplicates: {skipped_duplicate_books_count})")
    print(f"   - Imported Book Offsets: {imported_offsets_count} items")
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
    parser.add_argument("-d", "--db", choices=['general', 'adult'], default=None, help="Target DB type (default: from package manifest)")
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
