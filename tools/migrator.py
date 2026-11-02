# -*- coding: utf-8 -*-
import sqlite3
import os
import shutil
import sys
import hashlib
import re
from datetime import datetime

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.insert(0, MEDIA_SERVER_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(MEDIA_SERVER_DIR, ".env"))

import database

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_target_connection(db_type):
    """현재 .env의 DB_ENGINE 설정에 맞는 BookOasis DB 연결을 반환합니다."""
    return database.get_connection(db_type)


def get_target_engine_name():
    engine = os.environ.get("DB_ENGINE", os.environ.get("DBMS", "sqlite")).strip().lower()
    return "mariadb" if engine in ("mariadb", "mysql") else "sqlite"


def ensure_target_schema():
    """현재 엔진에 맞춰 최신 BookOasis 스키마를 보장합니다."""
    if get_target_engine_name() == "mariadb":
        from tools.db_schema_updater import run_schema_update

        run_schema_update()
        return
    database.init_databases()


def row_value(row, key, default=None):
    if row is None:
        return default
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def upsert_user_progress(cursor, book_id, pages_read, is_completed, last_read_at):
    cursor.execute(
        "SELECT id FROM user_progress WHERE book_id = ? AND user_id = 1",
        (book_id,),
    )
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            """
            UPDATE user_progress
            SET pages_read = ?, is_completed = ?, last_read_at = ?
            WHERE id = ?
            """,
            (pages_read, is_completed, last_read_at, row_value(existing, "id")),
        )
        return
    cursor.execute(
        """
        INSERT INTO user_progress
        (book_id, user_id, pages_read, is_completed, last_read_at)
        VALUES (?, 1, ?, ?, ?)
        """,
        (book_id, pages_read, is_completed, last_read_at),
    )

def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,)
    ).fetchone()
    return row is not None

def normalize_fs_path(path):
    return str(path or "").strip().replace("\\", "/")

def prompt_yes_no(message, default=True):
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{message} ({suffix})\n> ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes", "1", "true", "t", "ㅇ", "예", "네")

def get_kavita_library_folder_paths(conn):
    if not table_exists(conn, "FolderPath"):
        return {}

    rows = conn.execute("""
        SELECT l.Name AS LibraryName, fp.Path AS FolderPath
        FROM Library l
        JOIN FolderPath fp ON fp.LibraryId = l.Id
        WHERE COALESCE(fp.Path, '') != ''
        ORDER BY l.Id, fp.Id
    """).fetchall()

    paths_by_library = {}
    for row in rows:
        lib_name = row["LibraryName"]
        folder_path = normalize_fs_path(row["FolderPath"])
        if not folder_path:
            continue
        paths_by_library.setdefault(lib_name, [])
        if folder_path not in paths_by_library[lib_name]:
            paths_by_library[lib_name].append(folder_path)

    return {
        lib_name: "\n".join(paths)
        for lib_name, paths in paths_by_library.items()
        if paths
    }

def infer_library_common_path(paths):
    clean_paths = [normalize_fs_path(path) for path in paths if normalize_fs_path(path)]
    if not clean_paths:
        return ""
    if "\\" in paths[0]:
        return os.path.dirname(os.path.commonprefix(paths)).replace("\\", "/")
    return os.path.commonpath(clean_paths)

def build_people_subquery(conn, role, alias):
    if table_exists(conn, "SeriesMetadataPeople"):
        return f"""
        (SELECT GROUP_CONCAT(pe.Name, ', ')
         FROM SeriesMetadataPeople smp
         JOIN Person pe ON smp.PersonId = pe.Id
         JOIN SeriesMetadata sm ON smp.SeriesMetadataId = sm.Id
         WHERE sm.SeriesId = s.Id AND smp.Role = {role}) AS {alias}"""

    return f"""
        (SELECT GROUP_CONCAT(pe.Name, ', ')
         FROM PersonSeriesMetadata psm
         JOIN Person pe ON psm.PeopleId = pe.Id
         JOIN SeriesMetadata sm ON psm.SeriesMetadatasId = sm.Id
         WHERE sm.SeriesId = s.Id AND pe.Role = {role}) AS {alias}"""

def is_kavita_placeholder_value(value):
    text = str(value or "").strip()
    if not text:
        return True
    try:
        return float(text) <= -100000
    except ValueError:
        return False

def clean_kavita_title_part(value):
    text = str(value or "").strip()
    if is_kavita_placeholder_value(text):
        return ""
    return text

def build_file_title(file_path):
    title = os.path.splitext(os.path.basename(file_path or ""))[0].strip()
    title = re.sub(r"#\d+$", "", title).strip()
    title = re.sub(r"^(?:\[[^\]]+\]\s*)+", "", title).strip()
    return title

def build_book_title(row):
    volume_name = clean_kavita_title_part(row["VolumeName"])
    chapter_title = clean_kavita_title_part(row["ChapterTitle"])
    file_title = build_file_title(row["FilePath"])

    if chapter_title:
        if volume_name and chapter_title != volume_name:
            title = f"{volume_name} - {chapter_title}"
        else:
            title = chapter_title
    elif volume_name:
        title = file_title or volume_name
    else:
        title = file_title

    if not title:
        title = str(row["SeriesName"] or "").strip()
    if not title:
        title = os.path.splitext(os.path.basename(row["FilePath"] or ""))[0]
    return title

def convert_and_copy_cover(source_cover_name, kavita_covers_dir, bookoasis_covers_dir, file_path, library_id=None):
    """Kavita 커버를 가져와 BookOasis 표준 WebP 및 경로 해시 규격으로 변환하여 저장"""
    if not source_cover_name:
        return None
        
    source_path = os.path.join(kavita_covers_dir, source_cover_name)
    if not os.path.exists(source_path):
        return None
        
    # BookOasis 표준 파일 경로 기준 MD5 해시 파일명
    book_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    cover_filename = f"book_{book_hash}.webp"
    
    if library_id is not None:
        dest_dir = os.path.join(bookoasis_covers_dir, str(library_id))
        db_cover_path = f"{library_id}/{cover_filename}"
    else:
        dest_dir = bookoasis_covers_dir
        db_cover_path = cover_filename
        
    os.makedirs(dest_dir, exist_ok=True)
    target_path = os.path.join(dest_dir, cover_filename)
    
    try:
        # Pillow를 활용하여 WebP 포맷 변환 저장
        from PIL import Image
        from utils.safe_image import open_image
        with open_image(source_path) as img:
            img.save(target_path, "WEBP", quality=80)
        return db_cover_path
    except Exception as e:
        # 변환 실패 시 일반 바이너리 복사 Fallback
        try:
            shutil.copy2(source_path, target_path)
            return db_cover_path
        except Exception:
            return None

def run_kavita_to_bookoasis():
    print("\n==================================================")
    print(" 🛠️  [Step 2] Kavita -> BookOasis migration settings")
    print("==================================================")
    
    # 1. Kavita DB 경로 획득
    default_kavita_db = "C:/project/media_server/test/kavita.db"
    if not os.path.exists(default_kavita_db):
        default_kavita_db = "/home/az001a/Kavita/config/kavita.db"
        
    kavita_db_input = input(f"Enter the Kavita DB path and file name (default: {default_kavita_db})\n> ").strip()
    kavita_db_path = kavita_db_input if kavita_db_input else default_kavita_db
    
    if not os.path.exists(kavita_db_path):
        print(f"❌ Error: kavita.db does not exist at the given path: {kavita_db_path}")
        return

    # 2. Kavita Cover 경로 유추 및 획득
    migrate_covers = prompt_yes_no("Also import Kavita covers?", True)
    kavita_covers_dir = None
    if migrate_covers:
        kavita_dir = os.path.dirname(kavita_db_path)
        default_covers_dir = os.path.join(kavita_dir, "covers").replace('\\', '/')

        covers_input = input(f"The Kavita cover path is: {default_covers_dir}\nPress Enter if correct, or type a path to change it\n> ").strip()
        kavita_covers_dir = covers_input if covers_input else default_covers_dir

    print("\n==================================================")
    print(" 🛠️  [Step 3] BookOasis root settings")
    print("==================================================")
    
    # 3. BookOasis 루트 경로 획득
    default_oasis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\', '/')
    oasis_root_input = input(f"Enter the BookOasis root path ({default_oasis_root})\nPress Enter if correct, or type 1 to change it\n> ").strip()
    
    oasis_root = default_oasis_root
    if oasis_root_input == '1':
        oasis_root = input("Enter the BookOasis root path to use:\n> ").strip().replace('\\', '/')

    covers_dir = os.path.join(oasis_root, 'covers')

    try:
        ensure_target_schema()
    except Exception as init_error:
        print(f"❌ Error: failed to initialize/connect to the BookOasis database: {init_error}")
        print("Check DB_ENGINE and the MariaDB connection settings in .env.")
        return

    print("\n==================================================")
    print(" 🚀 [Step 4] Running the Kavita -> BookOasis migration")
    print("==================================================")
    
    kavita_conn = get_db_connection(kavita_db_path)
    general_conn = get_target_connection('general')
    
    kavita_cursor = kavita_conn.cursor()
    general_cursor = general_conn.cursor()

    authors_subquery = build_people_subquery(kavita_conn, 3, "Authors")
    publisher_subquery = build_people_subquery(kavita_conn, 10, "Publisher")
    
    query = f"""
    SELECT 
        l.Name AS LibraryName,
        s.Name AS SeriesName,
        v.Name AS VolumeName,
        c.Title AS ChapterTitle,
        m.FilePath,
        m.Pages AS TotalPages,
        p.PagesRead,
        p.LastModified AS ProgressLastModified,
        c.CoverImage AS ChapterCover,
        v.CoverImage AS VolumeCover,
        s.CoverImage AS SeriesCover,
        {authors_subquery},
        {publisher_subquery},
        (SELECT CASE WHEN sm.ReleaseYear > 0 THEN sm.ReleaseYear || '-01-01' ELSE NULL END 
         FROM SeriesMetadata sm 
         WHERE sm.SeriesId = s.Id LIMIT 1) AS ReleaseDate,
        (SELECT sm.Summary 
         FROM SeriesMetadata sm 
         WHERE sm.SeriesId = s.Id LIMIT 1) AS Summary,
        (SELECT GROUP_CONCAT(g.Title, ', ')
         FROM GenreSeriesMetadata gsm 
         JOIN Genre g ON gsm.GenresId = g.Id 
         JOIN SeriesMetadata sm ON gsm.SeriesMetadatasId = sm.Id 
         WHERE sm.SeriesId = s.Id) AS Genres,
        (SELECT GROUP_CONCAT(t.Title, ', ') 
         FROM SeriesMetadataTag smt 
         JOIN Tag t ON smt.TagsId = t.Id 
         JOIN SeriesMetadata sm ON smt.SeriesMetadatasId = sm.Id 
         WHERE sm.SeriesId = s.Id) AS Tags
    FROM MangaFile m
    JOIN Chapter c ON m.ChapterId = c.Id
    JOIN Volume v ON c.VolumeId = v.Id
    JOIN Series s ON v.SeriesId = s.Id
    JOIN Library l ON s.LibraryId = l.Id
    LEFT JOIN (
        SELECT ChapterId, MAX(PagesRead) AS PagesRead, MAX(LastModified) AS LastModified
        FROM AppUserProgresses
        GROUP BY ChapterId
    ) p ON c.Id = p.ChapterId
    """
    
    try:
        kavita_cursor.execute(query)
        rows = kavita_cursor.fetchall()
        total_rows = len(rows)
        print(f"[*] Loaded {total_rows} books from the Kavita DB.")
        
        # 1차: 라이브러리 목록 매핑 및 생성
        library_paths_map = {}
        for row in rows:
            lib_name = row['LibraryName']
            if lib_name not in library_paths_map:
                library_paths_map[lib_name] = []
            library_paths_map[lib_name].append(row['FilePath'])

        configured_library_paths = get_kavita_library_folder_paths(kavita_conn)

        library_cache = {}
        for lib_name, paths in library_paths_map.items():
            if not paths:
                continue
            common_path = configured_library_paths.get(lib_name) or infer_library_common_path(paths)

            general_cursor.execute("SELECT id FROM libraries WHERE name = ?", (lib_name,))
            db_lib_row = general_cursor.fetchone()
            if db_lib_row:
                lib_id = row_value(db_lib_row, "id")
                general_cursor.execute("UPDATE libraries SET physical_path = ? WHERE id = ?", (common_path, lib_id))
            else:
                general_cursor.execute(
                    """
                    INSERT INTO libraries (
                        name, physical_path, scan_status, is_remote,
                        vfs_refresh_before_scan, icon, color, hide_cover
                    ) VALUES (?, ?, 'ready', 0, 0, 'fa-book', '#94a3b8', 0)
                    """,
                    (lib_name, common_path),
                )
                lib_id = general_cursor.lastrowid
            library_cache[lib_name] = lib_id
            
        general_conn.commit()
        print("[+] Library path mapping and setup done.")
        
        # 2차: 책 정보 이관 및 커버 이미지 변환
        migrated_books = 0
        success_covers = 0
        
        for idx, row in enumerate(rows):
            lib_name = row['LibraryName']
            file_path = row['FilePath']
            lib_id = library_cache[lib_name]
            
            _, ext = os.path.splitext(file_path)
            file_format = ext.replace('.', '').lower() or 'zip'
            
            title = build_book_title(row)
            series_name = row['SeriesName']
            total_pages = row['TotalPages'] or 0
            
            cover_image_name = None
            saved_cover_name = None
            if migrate_covers:
                # 물리적으로 실제 존재하는 파일만 우선순위별로 탐색 (Chapter -> Volume -> Series)
                for cov_name in [row['ChapterCover'], row['VolumeCover'], row['SeriesCover']]:
                    if cov_name:
                        check_path = os.path.join(kavita_covers_dir, cov_name)
                        if os.path.exists(check_path):
                            cover_image_name = cov_name
                            break

                saved_cover_name = convert_and_copy_cover(cover_image_name, kavita_covers_dir, covers_dir, file_path, lib_id)
            if saved_cover_name:
                success_covers += 1
                
            # 메타데이터 추출 및 매핑
            authors = row['Authors'] or "Kavita Author"
            publisher = row['Publisher'] or "Kavita Publisher"
            genre = row['Genres']
            tags = row['Tags']
            summary = row['Summary']
            
            # 발매일 파싱 교정 (Kavita는 datetime 형식으로 올 수 있으므로 YYYY-MM-DD 포맷 파싱)
            release_date = row['ReleaseDate']
            if release_date:
                try:
                    dt = datetime.fromisoformat(release_date.split('T')[0])
                    release_date = dt.strftime('%Y-%m-%d')
                except Exception:
                    pass

            # 도서 정보 삽입 또는 갱신. 재마이그레이션 시 기존 제목/메타데이터도 교정한다.
            general_cursor.execute("SELECT id, cover_image FROM books WHERE file_path = ?", (file_path,))
            existing_book = general_cursor.fetchone()
            if existing_book:
                book_id = row_value(existing_book, "id")
                cover_to_save = saved_cover_name or row_value(existing_book, "cover_image")
                general_cursor.execute(
                    """
                    UPDATE books
                    SET library_id = ?, title = ?, series_name = ?, author = ?, publisher = ?,
                        file_format = ?, cover_image = ?, total_pages = ?, genre = ?, tags = ?,
                        summary = ?, release_date = ?
                    WHERE id = ?
                    """,
                    (lib_id, title, series_name, authors, publisher, file_format, cover_to_save,
                     total_pages, genre, tags, summary, release_date, book_id)
                )
            else:
                general_cursor.execute(
                    """
                    INSERT INTO books
                    (library_id, title, series_name, author, publisher, file_path, file_format, cover_image, total_pages, genre, tags, summary, release_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (lib_id, title, series_name, authors, publisher, file_path, file_format, saved_cover_name, total_pages, genre, tags, summary, release_date)
                )
                book_id = general_cursor.lastrowid
            
            # 진척도 정보 동기화 이관
            pages_read = row['PagesRead']
            if pages_read and pages_read > 0:
                is_completed = 1 if pages_read >= total_pages else 0
                last_modified = row['ProgressLastModified'] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                upsert_user_progress(
                    general_cursor,
                    book_id,
                    pages_read,
                    is_completed,
                    last_modified,
                )
                    
            migrated_books += 1
            if migrated_books % 500 == 0 or migrated_books == total_rows:
                print(f"[*] Progress: {migrated_books} / {total_rows} books processed...")
                general_conn.commit()

        general_conn.commit()
                
        print("\n==================================================")
        print(" ✨ Migration report")
        print("==================================================")
        print(f"- Books migrated: {migrated_books}")
        print(f"- Target database engine: {get_target_engine_name()}")
        if migrate_covers:
            print(f"- Covers converted to WebP: {success_covers}")
        else:
            print("- Cover import: skipped")
        print("Migration finished successfully.")
        
    except Exception as ex:
        try:
            general_conn.rollback()
        except Exception:
            pass
        print(f"❌ Exception during migration: {ex}")
    finally:
        kavita_conn.close()
        general_conn.close()

def run_bookoasis_to_bookoasis():
    print("\n==================================================")
    print(" 🛠️  [Step 2] BookOasis -> BookOasis path replacement settings")
    print("==================================================")
    
    # 1. BookOasis 루트 경로 획득
    default_oasis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\', '/')
    oasis_root_input = input(f"Enter the BookOasis root path ({default_oasis_root})\nPress Enter if correct, or type a path to change it\n> ").strip()
    oasis_root = oasis_root_input if oasis_root_input else default_oasis_root
    
    covers_dir = os.path.join(oasis_root, 'covers')

    try:
        ensure_target_schema()
    except Exception as init_error:
        print(f"❌ Error: failed to initialize/connect to the BookOasis database: {init_error}")
        return

    # 2. 경로 교체 규칙 획득
    old_prefix = input("Enter the old path prefix to replace (Old Prefix):\ne.g. /home/az001a/Script/media_server\n> ").strip()
    new_prefix = input("Enter the new path prefix (New Prefix):\ne.g. C:/project/media_server\n> ").strip()
    
    if not old_prefix or not new_prefix:
        print("❌ Error: the old/new paths to replace cannot be empty.")
        return

    print(f"\nTarget DB engine: {get_target_engine_name()}")
    print(f"Old path: {old_prefix}")
    print(f"New path: {new_prefix}")
    if not prompt_yes_no("Change the general/adult/audiobook paths using the rule above?", False):
        print("Path change cancelled.")
        return

    print("\n==================================================")
    print(" 🚀 [Step 3] Replacing paths and renaming cover hashes")
    print("==================================================")
    
    target_db_types = ('general', 'adult', 'audiobook')
    for db_type in target_db_types:
        print(f"\n[*] Processing database: {db_type} ({get_target_engine_name()})")

        conn = get_target_connection(db_type)
        cursor = conn.cursor()
        
        try:
            # 1. 라이브러리 물리 경로 갱신
            cursor.execute("SELECT id, name, physical_path FROM libraries")
            libraries = cursor.fetchall()
            for lib in libraries:
                if lib['physical_path'] and old_prefix in lib['physical_path']:
                    updated_path = lib['physical_path'].replace(old_prefix, new_prefix)
                    cursor.execute("UPDATE libraries SET physical_path = ? WHERE id = ?", (updated_path, lib['id']))
                    print(f"  └ Library [{lib['name']}] path changed: {lib['physical_path']} -> {updated_path}")
            
            if db_type == 'audiobook':
                cursor.execute("SELECT id, folder_path FROM audiobooks")
                audiobooks = cursor.fetchall()
                updated_audiobooks_count = 0
                for audiobook in audiobooks:
                    folder_path = row_value(audiobook, 'folder_path', '')
                    if not folder_path or old_prefix not in folder_path:
                        continue
                    new_folder_path = folder_path.replace(old_prefix, new_prefix)
                    cursor.execute(
                        "UPDATE audiobooks SET folder_path = ? WHERE id = ?",
                        (new_folder_path, row_value(audiobook, 'id')),
                    )
                    updated_audiobooks_count += 1

                cursor.execute("SELECT id, file_path FROM audiobook_tracks")
                tracks = cursor.fetchall()
                updated_tracks_count = 0
                for track in tracks:
                    file_path = row_value(track, 'file_path', '')
                    if not file_path or old_prefix not in file_path:
                        continue
                    cursor.execute(
                        "UPDATE audiobook_tracks SET file_path = ? WHERE id = ?",
                        (file_path.replace(old_prefix, new_prefix), row_value(track, 'id')),
                    )
                    updated_tracks_count += 1

                conn.commit()
                print(
                    f"  [+] Done: updated {updated_audiobooks_count} audiobook folder paths and "
                    f"{updated_tracks_count} track file paths."
                )
                continue

            # 2. 일반/성인 도서 목록 조회 및 커버 리네임 작업
            cursor.execute("SELECT id, file_path, cover_image, library_id FROM books")
            books = cursor.fetchall()
            
            updated_books_count = 0
            renamed_covers_count = 0
            
            for b in books:
                file_path = row_value(b, 'file_path', '')
                if not file_path or old_prefix not in file_path:
                    continue
                    
                # 신규 파일 경로 구함
                new_file_path = file_path.replace(old_prefix, new_prefix)
                
                # 커버 이미지 해시 리네임 연계 처리
                cover_image = row_value(b, 'cover_image')
                new_cover_image = cover_image
                
                if cover_image and not cover_image.startswith('series_'):
                    # 기존 해시 파일명
                    old_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
                    # 새 해시 파일명
                    new_hash = hashlib.md5(new_file_path.encode('utf-8')).hexdigest()
                    
                    old_cover_filename = f"book_{old_hash}.webp"
                    new_cover_filename = f"book_{new_hash}.webp"
                    
                    lib_id = row_value(b, 'library_id')
                    if lib_id:
                        old_phys_path = os.path.join(covers_dir, str(lib_id), old_cover_filename)
                        new_phys_path = os.path.join(covers_dir, str(lib_id), new_cover_filename)
                        new_cover_image = f"{lib_id}/{new_cover_filename}"
                    else:
                        old_phys_path = os.path.join(covers_dir, old_cover_filename)
                        new_phys_path = os.path.join(covers_dir, new_cover_filename)
                        new_cover_image = new_cover_filename
                        
                    # 실제 로컬 디스크 상 물리 표지 파일 리네임 수행
                    if os.path.exists(old_phys_path):
                        try:
                            # 새 파일 경로에 폴더가 없을 경우 생성 방어
                            os.makedirs(os.path.dirname(new_phys_path), exist_ok=True)
                            os.rename(old_phys_path, new_phys_path)
                            renamed_covers_count += 1
                        except Exception as e:
                            print(f"  └ [Cover file rename failed] {old_cover_filename} -> {new_cover_filename}: {e}")
                            
                # DB 데이터 업데이트 쿼리 반영
                cursor.execute(
                    "UPDATE books SET file_path = ?, cover_image = ? WHERE id = ?",
                    (new_file_path, new_cover_image, row_value(b, 'id'))
                )
                updated_books_count += 1
                
            conn.commit()
            print(f"  [+] Done: updated {updated_books_count} book paths and renamed {renamed_covers_count} cover hash files.")
            
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"❌ Error while processing {db_type}: {e}")
        finally:
            conn.close()
            
    print("\n==================================================")
    print(" ✨ Path and cover replacement finished successfully.")
    print("==================================================")

def main():
    print("==================================================")
    print(" 📊 BookOasis data migration and management (v2.0)")
    print("==================================================")
    print(" [Step 1] Choose a migration mode:")
    print(f"  Current target DB engine: {get_target_engine_name()}")
    print("  1. Kavita -> BookOasis migration (SQLite/MariaDB)")
    print("  2. BookOasis -> BookOasis (replace general/adult/audiobook paths)")
    
    choice = input("\n>> Enter a menu number and press Enter (default: 1)\n> ").strip()
    if not choice:
        choice = '1'
        
    if choice == '1':
        run_kavita_to_bookoasis()
    elif choice == '2':
        run_bookoasis_to_bookoasis()
    else:
        print("❌ Invalid menu choice. Exiting.")

if __name__ == '__main__':
    main()
