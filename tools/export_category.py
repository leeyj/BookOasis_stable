# -*- coding: utf-8 -*-
"""
tools/export_category.py
------------------------------------------------
BookOasis 카테고리(라이브러리) 메타데이터 및 커버 이미지 내보내기 (Export) CLI 도구
(단일 및 다중 물리 디렉토리 경로 & 다중 카테고리 일괄 내보내기 Batch Export 지원)
"""

import os
import sys
import json
import argparse
import sqlite3
import zipfile
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

def parse_root_paths(raw_path):
    if not raw_path:
        return []
    lines = raw_path.replace('\r', '').replace(';', '\n').split('\n')
    paths = [p.strip() for p in lines if p.strip()]
    return paths

def parse_library_ids(raw_args):
    ids = []
    if not raw_args:
        return ids
    if isinstance(raw_args, (int, str)):
        raw_args = [raw_args]

    for item in raw_args:
        parts = str(item).replace(',', ' ').replace(';', ' ').split()
        for p in parts:
            try:
                val = int(p)
                if val not in ids:
                    ids.append(val)
            except ValueError:
                pass
    return ids

def export_single_category(db_type, library_id, output_path=None):
    print(f"\n[*] Processing Category ID '{library_id}' from DB '{db_type}'...")

    conn = get_db_connection(db_type)
    cursor = conn.cursor()

    # 1. 라이브러리 조회
    cursor.execute("SELECT * FROM libraries WHERE id = ?", (library_id,))
    lib_row = cursor.fetchone()
    if not lib_row:
        conn.close()
        print(f"[!] Error: Library ID {library_id} not found in {db_type} database. Skipping.")
        return False

    library = dict(lib_row)
    lib_name = library['name']
    raw_physical_path = library.get('physical_path', '')
    root_paths = parse_root_paths(raw_physical_path)

    print(f"[+] Target Library: '{lib_name}' (ID: {library_id})")
    print(f"[+] Root Physical Paths count: {len(root_paths)}")
    for idx, rp in enumerate(root_paths):
        print(f"    [{idx}] {rp}")

    # 2. 도서 목록 조회 (is_deleted가 1인 항목 제외)
    cursor.execute("SELECT * FROM books WHERE library_id = ? AND (is_deleted IS NULL OR is_deleted = 0)", (library_id,))
    book_rows = cursor.fetchall()
    books = [dict(r) for r in book_rows]
    print(f"[+] Found {len(books)} books in library.")

    # 3. root_index 판별, relative_path 계산 및 offset 수집
    books_payload = []
    offsets_payload = {}
    cover_files_to_pack = set()

    for idx, b in enumerate(books):
        book_id = b['id']
        abs_file_path = b['file_path']

        matched_root_idx = 0
        rel_path = None

        norm_f_path = os.path.normpath(abs_file_path).lower()

        for r_idx, r_path in enumerate(root_paths):
            norm_r_path = os.path.normpath(r_path).lower()
            if norm_f_path.startswith(norm_r_path):
                matched_root_idx = r_idx
                try:
                    rel_path = os.path.relpath(abs_file_path, r_path).replace('\\', '/')
                except ValueError:
                    rel_path = os.path.basename(abs_file_path)
                break

        if rel_path is None:
            base_ref = root_paths[0] if root_paths else ""
            try:
                rel_path = os.path.relpath(abs_file_path, base_ref).replace('\\', '/')
            except ValueError:
                rel_path = os.path.basename(abs_file_path)

        b_copy = dict(b)
        b_copy['root_index'] = matched_root_idx
        b_copy['relative_path'] = rel_path
        books_payload.append(b_copy)

        # 커버 이미지 파일 수집
        cover_img = b.get('cover_image')
        if cover_img:
            clean_cover = str(cover_img).replace('\\', '/').lstrip('/')
            cover_candidates = []
            if os.path.isabs(cover_img):
                cover_candidates.append(cover_img)

            cover_candidates.append(os.path.join(BASE_DIR, clean_cover))
            cover_candidates.append(os.path.join(BASE_DIR, 'covers', clean_cover))
            if clean_cover.startswith('covers/'):
                unprefixed = clean_cover[7:]
                cover_candidates.append(os.path.join(BASE_DIR, 'covers', unprefixed))
                cover_candidates.append(os.path.join(BASE_DIR, unprefixed))
            cover_candidates.append(os.path.join(BASE_DIR, 'covers', str(library_id), os.path.basename(clean_cover)))
            cover_candidates.append(os.path.join(BASE_DIR, 'covers', os.path.basename(clean_cover)))

            for cand in cover_candidates:
                norm_cand = os.path.normpath(cand)
                if os.path.exists(norm_cand) and os.path.isfile(norm_cand):
                    cover_files_to_pack.add(norm_cand)
                    break

        # offset 데이터 수집
        cursor.execute("SELECT page_idx, filename, local_header_offset, compress_size, file_size, compress_type FROM book_offsets WHERE book_id = ?", (book_id,))
        offset_rows = cursor.fetchall()
        if offset_rows:
            offsets_payload[idx] = [dict(o) for o in offset_rows]

    conn.close()

    # 4. 고유 아카이브 파일명 생성 ({카테고리명}_{db_type}_lib{id}_{YYYYMMDD_HHMMSS}.oasis.zip)
    safe_name = "".join(c for c in lib_name if c.isalnum() or c in ('_', '-')).strip()
    if not safe_name:
        safe_name = f"category_{library_id}"
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    default_filename = f"{safe_name}_{db_type}_lib{library_id}_{date_str}.oasis.zip"

    final_output_path = None
    if output_path:
        # output_path가 디렉토리이거나 확장자가 .zip이 아닌 경우 디렉토리로 취급
        if os.path.isdir(output_path) or not output_path.endswith('.zip'):
            os.makedirs(output_path, exist_ok=True)
            final_output_path = os.path.join(output_path, default_filename)
        else:
            final_output_path = output_path
    else:
        final_output_path = os.path.join(BASE_DIR, default_filename)

    # 5. 매니페스트 및 메타데이터 작성
    manifest = {
        "export_version": "1.2",
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "db_type": db_type,
        "library_id": library_id,
        "library_name": lib_name,
        "root_paths_count": len(root_paths),
        "books_count": len(books_payload),
        "covers_count": len(cover_files_to_pack)
    }

    metadata = {
        "library": {
            "id": library_id,
            "name": library['name'],
            "physical_paths": root_paths,
            "cron_schedule": library.get('cron_schedule'),
            "icon": library.get('icon', 'fa-book'),
            "color": library.get('color', '#94a3b8'),
            "hide_cover": library.get('hide_cover', 0)
        },
        "books": books_payload,
        "offsets": offsets_payload
    }

    # 6. ZIP 패키징 (이미지 파일 재압축으로 인한 CPU 점유를 막기 위해 ZIP_STORED 단순 묶음 적용)
    print(f"[*] Packaging data into '{final_output_path}' (ZIP_STORED)...")
    os.makedirs(os.path.dirname(os.path.abspath(final_output_path)), exist_ok=True)

    with zipfile.ZipFile(final_output_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
        zipf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zipf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))

        covers_base = os.path.join(BASE_DIR, 'covers')
        for cover_path in cover_files_to_pack:
            try:
                rel_cover = os.path.relpath(cover_path, covers_base).replace('\\', '/')
                arcname = os.path.join("covers", rel_cover)
            except ValueError:
                arcname = os.path.join("covers", os.path.basename(cover_path))
            zipf.write(cover_path, arcname=arcname)

    file_size_mb = os.path.getsize(final_output_path) / (1024 * 1024)
    print("==========================================================")
    print(f"✨ Category Export Successfully Completed!")
    print(f"   - Export File: {final_output_path} ({file_size_mb:.2f} MB)")
    print(f"   - Category Name: {lib_name} (ID: {library_id})")
    print(f"   - Total Books: {len(books_payload)} items")
    print(f"   - Total Covers Packed: {len(cover_files_to_pack)} files")
    print("==========================================================")
    return True


def export_categories(db_type, raw_library_ids, output_path=None):
    lib_ids = parse_library_ids(raw_library_ids)
    if not lib_ids:
        print("[!] Error: No valid library ID specified.")
        sys.exit(1)

    print(f"[*] Starting Batch Category Export for {len(lib_ids)} categories: {lib_ids}")
    success_count = 0
    for lid in lib_ids:
        # 다중 내보내기 시 output_path가 파일 형태면 개별 디렉터리로 전환
        out_target = output_path
        if len(lib_ids) > 1 and output_path and output_path.endswith('.zip'):
            out_target = os.path.dirname(output_path) or BASE_DIR

        if export_single_category(db_type=db_type, library_id=lid, output_path=out_target):
            success_count += 1

    print(f"\n🎉 Batch Export Finished: {success_count} / {len(lib_ids)} categories exported successfully.")


def main():
    parser = argparse.ArgumentParser(description="BookOasis Category Export CLI Tool (Multi-path & Batch Export Supported)")
    parser.add_argument("-d", "--db", choices=['general', 'adult'], default='general', help="Target Database (general or adult)")
    parser.add_argument("-l", "--library-id", nargs='+', required=True, help="Library ID(s) to export. Multiple IDs or comma-separated supported (e.g. -l 15 18 21)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output .oasis.zip file or destination directory path")

    args = parser.parse_args()
    export_categories(db_type=args.db, raw_library_ids=args.library_id, output_path=args.output)


if __name__ == '__main__':
    main()
