# -*- coding: utf-8 -*-
"""
tools/import_category.py
------------------------------------------------
BookOasis 카테고리(라이브러리) 메타데이터 및 커버 이미지 가져오기 (Import) CLI 도구
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
        # 쉼표(,), 세미콜론(;), 줄바꿈(\n) 단위로 파싱
        parts = item.replace('\r', '').replace(';', '\n').replace(',', '\n').split('\n')
        for sub in parts:
            cleaned = sub.strip()
            if cleaned:
                result.append(os.path.abspath(cleaned))
    return result

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
    print(f"👉 Import Recommendation:")
    print(f"   Please provide {orig_root_count} target path(s) (-p) when importing this package!")
    print("==========================================================")


def import_category(input_path, target_paths_raw, db_type=None, name=None):
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
    target_lib_name = name if name else metadata.get('library', {}).get('name', 'Imported Library')

    lib_info = metadata.get('library', {})
    orig_root_paths = lib_info.get('physical_paths', [])
    orig_root_count = manifest.get('root_paths_count', len(orig_root_paths))
    print(f"[+] Package Metadata:")
    print(f"    - Original Name: {manifest.get('library_name')}")
    print(f"    - Original Root Paths Count: {orig_root_count} entries")
    if orig_root_paths:
        for idx, rp in enumerate(orig_root_paths):
            print(f"      [{idx}] {rp}")
    print(f"    - Target DB Type: {target_db_type}")
    print(f"    - Target Category Name: {target_lib_name}")
    print(f"    - Target Physical Paths ({len(target_paths)} provided):")
    for idx, tp in enumerate(target_paths):
        print(f"      [{idx}] {tp}")
    print(f"      (💡 Tip: [웹 UI의 카테고리 관리에서 입력하는 경로] <─── 100% 동일 ───> [-p 옵션 경로])")
    print(f"      (예시: -p \"/volume1/mnt/GDDRIVE/READING/만화/완결A\")")

    if orig_root_count > len(target_paths):
        print(f"[!] Warning: Package has {orig_root_count} root paths, but only {len(target_paths)} target paths provided.")
        print(f"    Unmatched index items will fall back to target path [0]: {target_paths[0]}")

    # 1. 대상 디렉터리 존재 검사 및 자동 생성
    for tp in target_paths:
        if not os.path.exists(tp):
            try:
                os.makedirs(tp, exist_ok=True)
                print(f"[+] Created target directory: {tp}")
            except Exception as e:
                print(f"[!] Error creating target directory '{tp}': {e}")

    conn = get_db_connection(target_db_type)
    cursor = conn.cursor()

    # 2. 카테고리(libraries) 생성 (이름 중복 방지 처리)
    cursor.execute("SELECT id FROM libraries WHERE name = ?", (target_lib_name,))
    existing_lib = cursor.fetchone()
    if existing_lib:
        target_lib_name = f"{target_lib_name} (Imported {datetime.datetime.now().strftime('%H%M%S')})"
        print(f"[!] Library name collision detected. Renamed category to: '{target_lib_name}'")

    db_physical_path = "\n".join(target_paths)
    lib_meta = metadata.get('library', {})

    cursor.execute("""
        INSERT INTO libraries (name, physical_path, cron_schedule, icon, color, hide_cover)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        target_lib_name,
        db_physical_path,
        lib_meta.get('cron_schedule'),
        lib_meta.get('icon', 'fa-book'),
        lib_meta.get('color', '#94a3b8'),
        lib_meta.get('hide_cover', 0)
    ))
    new_library_id = cursor.lastrowid
    conn.commit()
    print(f"[+] Created new library in DB (ID: {new_library_id})")

    # 3. 커버 이미지 복원 (신규 library_id 폴더 하위로 정형화)
    covers_dir = os.path.join(BASE_DIR, 'covers')
    lib_covers_dir = os.path.join(covers_dir, str(new_library_id))
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

    # 4. 도서(books) 및 offset 데이터 일괄 복원 (root_index 기준 매핑)
    books_list = metadata.get('books', [])
    offsets_dict = metadata.get('offsets', {})

    imported_books_count = 0
    imported_offsets_count = 0

    for idx, b in enumerate(books_list):
        rel_path = b.get('relative_path', '')
        if not rel_path:
            continue

        root_idx = b.get('root_index', 0)
        # root_index에 매칭되는 target_path 선택
        if root_idx < len(target_paths):
            selected_target_root = target_paths[root_idx]
        else:
            selected_target_root = target_paths[0]

        # OS 패스 구분자에 맞춰 신규 절대 경로 합성
        clean_rel = rel_path.replace('/', os.sep).replace('\\', os.sep)
        new_file_path = os.path.normpath(os.path.join(selected_target_root, clean_rel))

        cover_img = b.get('cover_image', '')
        if cover_img:
            filename = os.path.basename(cover_img)
            cover_img = f"{new_library_id}/{filename}"

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor.execute("""
                INSERT INTO books (
                    library_id, title, series_name, author, isbn, file_path, file_format,
                    total_pages, has_offsets, cover_image, publisher, link, score,
                    release_date, summary, genre, tags, is_favorite, cover_updated_at,
                    created_at, metadata_locked, file_mtime, file_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_library_id,
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
            print(f"[!] Warning: Skipping duplicate book file: {new_file_path}")
            continue
        except Exception as b_err:
            print(f"[!] Error inserting book '{b.get('title')}': {b_err}")
            continue

    conn.commit()
    conn.close()

    print("==========================================================")
    print(f"✨ Category Import Successfully Completed!")
    print(f"   - New Library ID: {new_library_id}")
    print(f"   - Library Name: {target_lib_name}")
    print(f"   - Physical Paths ({len(target_paths)} entries):")
    for tp in target_paths:
        print(f"     * {tp}")
    print(f"   - Imported Books: {imported_books_count} / {len(books_list)}")
    print(f"   - Imported Book Offsets: {imported_offsets_count} items")
    print(f"   - Restored Covers: {extracted_covers} files")
    print("==========================================================")


def main():
    parser = argparse.ArgumentParser(description="BookOasis Category Import CLI Tool (Multi-path Supported)")
    parser.add_argument("-i", "--input", type=str, required=True, help="Path to input .oasis.zip package")
    parser.add_argument("-p", "--target-path", action="append", default=None, help="New target physical path(s). Can be specified multiple times or separated by comma/newline")
    parser.add_argument("-d", "--db", choices=['general', 'adult'], default=None, help="Target DB type (default: from package manifest)")
    parser.add_argument("-n", "--name", type=str, default=None, help="New category name (default: from package manifest)")
    parser.add_argument("--info", "--inspect", action="store_true", help="Inspect package metadata and physical path requirements without importing")

    args = parser.parse_args()

    if args.info:
        inspect_package(args.input)
        return

    if not args.target_path:
        print("[!] Error: At least one target physical path (--target-path / -p) is required when importing.")
        print(f"    (Tip: Run 'python {sys.argv[0]} -i \"{args.input}\" --info' to inspect package requirements)")
        sys.exit(1)

    import_category(input_path=args.input, target_paths_raw=args.target_path, db_type=args.db, name=args.name)


if __name__ == '__main__':
    main()
