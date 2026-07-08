# -*- coding: utf-8 -*-
import sqlite3
import os
import shutil
import sys
import hashlib
from datetime import datetime
from PIL import Image

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,)
    ).fetchone()
    return row is not None

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

def is_kavita_placeholder_volume(value):
    text = str(value or "").strip()
    if not text:
        return True
    try:
        return float(text) <= -100000
    except ValueError:
        return False

def build_book_title(row):
    volume_name = str(row["VolumeName"] or "").strip()
    chapter_title = str(row["ChapterTitle"] or "").strip()

    if is_kavita_placeholder_volume(volume_name):
        title = chapter_title
    elif chapter_title and chapter_title != volume_name:
        title = f"{volume_name} - {chapter_title}"
    else:
        title = chapter_title or volume_name

    if not title:
        title = os.path.splitext(os.path.basename(row["FilePath"]))[0]
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
        with Image.open(source_path) as img:
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
    print(" 🛠️  [Step 2] Kavita ➡️ BookOasis 이관 설정")
    print("==================================================")
    
    # 1. Kavita DB 경로 획득
    default_kavita_db = "C:/project/media_server/test/kavita.db"
    if not os.path.exists(default_kavita_db):
        default_kavita_db = "/home/az001a/Kavita/config/kavita.db"
        
    kavita_db_input = input(f"Kavita DB 경로와 DB파일명을 입력하세요 (기본값: {default_kavita_db})\n> ").strip()
    kavita_db_path = kavita_db_input if kavita_db_input else default_kavita_db
    
    if not os.path.exists(kavita_db_path):
        print(f"❌ 에러: 지정된 경로에 kavita.db 파일이 존재하지 않습니다: {kavita_db_path}")
        return

    # 2. Kavita Cover 경로 유추 및 획득
    kavita_dir = os.path.dirname(kavita_db_path)
    default_covers_dir = os.path.join(kavita_dir, "covers").replace('\\', '/')
    
    covers_input = input(f"Kavita cover 경로는 다음과 같습니다 : {default_covers_dir}\n맞으면 엔터, 수정하려면 경로 입력\n> ").strip()
    kavita_covers_dir = covers_input if covers_input else default_covers_dir

    print("\n==================================================")
    print(" 🛠️  [Step 3] BookOasis 루트 설정")
    print("==================================================")
    
    # 3. BookOasis 루트 경로 획득
    default_oasis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\', '/')
    oasis_root_input = input(f"BookOasis의 루트 경로를 입력하세요 ({default_oasis_root})\n맞으면 엔터, 수정하려면 1 입력\n> ").strip()
    
    oasis_root = default_oasis_root
    if oasis_root_input == '1':
        oasis_root = input("수정할 BookOasis 루트 경로를 입력하세요:\n> ").strip().replace('\\', '/')

    db_dir = os.path.join(oasis_root, 'db')
    db_general_path = os.path.join(db_dir, 'media_general.db')
    covers_dir = os.path.join(oasis_root, 'covers')

    if not os.path.exists(db_general_path):
        print(f"❌ 에러: BookOasis 데이터베이스 파일이 존재하지 않습니다: {db_general_path}")
        print("서버를 먼저 가동하여 DB 스키마가 초기화된 후에 마이그레이터를 실행해 주세요.")
        return

    print("\n==================================================")
    print(" 🚀 [Step 4] Kavita ➡️ BookOasis 이관 작업 실행")
    print("==================================================")
    
    kavita_conn = get_db_connection(kavita_db_path)
    general_conn = get_db_connection(db_general_path)
    
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
    LEFT JOIN AppUserProgresses p ON c.Id = p.ChapterId
    """
    
    try:
        kavita_cursor.execute(query)
        rows = kavita_cursor.fetchall()
        total_rows = len(rows)
        print(f"[*] Kavita DB로부터 총 {total_rows}개의 도서 데이터를 로드했습니다.")
        
        # 1차: 라이브러리 목록 매핑 및 생성
        library_paths_map = {}
        for row in rows:
            lib_name = row['LibraryName']
            if lib_name not in library_paths_map:
                library_paths_map[lib_name] = []
            library_paths_map[lib_name].append(row['FilePath'])
            
        library_cache = {}
        for lib_name, paths in library_paths_map.items():
            if not paths:
                continue
            if '\\' in paths[0]:
                common_path = os.path.dirname(os.path.commonprefix(paths)).replace('\\', '/')
            else:
                common_path = os.path.commonpath(paths)
                
            general_cursor.execute("SELECT id FROM libraries WHERE name = ?", (lib_name,))
            db_lib_row = general_cursor.fetchone()
            if db_lib_row:
                lib_id = db_lib_row[0]
                general_cursor.execute("UPDATE libraries SET physical_path = ? WHERE id = ?", (common_path, lib_id))
            else:
                general_cursor.execute(
                    "INSERT INTO libraries (name, physical_path) VALUES (?, ?)",
                    (lib_name, common_path)
                )
                lib_id = general_cursor.lastrowid
            library_cache[lib_name] = lib_id
            
        general_conn.commit()
        print("[+] 라이브러리 경로 매핑 및 설정 완료.")
        
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
            
            # 물리적으로 실제 존재하는 파일만 우선순위별로 탐색 (Chapter -> Volume -> Series)
            cover_image_name = None
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

            # 도서 정보 삽입 (중복 경로 무시)
            general_cursor.execute(
                """
                INSERT OR IGNORE INTO books 
                (library_id, title, series_name, author, publisher, file_path, file_format, cover_image, total_pages, genre, tags, summary, release_date) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (lib_id, title, series_name, authors, publisher, file_path, file_format, saved_cover_name, total_pages, genre, tags, summary, release_date)
            )
            
            # 진척도 정보 동기화 이관
            pages_read = row['PagesRead']
            if pages_read and pages_read > 0:
                general_cursor.execute("SELECT id FROM books WHERE file_path = ?", (file_path,))
                book_row = general_cursor.fetchone()
                if book_row:
                    book_id = book_row[0]
                    is_completed = 1 if pages_read >= total_pages else 0
                    last_modified = row['ProgressLastModified'] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    general_cursor.execute(
                        """
                        INSERT OR REPLACE INTO user_progress 
                        (book_id, user_id, pages_read, is_completed, last_read_at) 
                        VALUES (?, 1, ?, ?, ?)
                        """,
                        (book_id, pages_read, is_completed, last_modified)
                    )
                    
            migrated_books += 1
            if migrated_books % 500 == 0 or migrated_books == total_rows:
                print(f"[*] 진행도: {migrated_books} / {total_rows} 권 처리 완료...")
                general_conn.commit()
                
        print("\n==================================================")
        print(" ✨ 이관 결과 리포트")
        print("==================================================")
        print(f"- 이관 성공 도서 권수: {migrated_books} 권")
        print(f"- WebP 변환 성공 표지: {success_covers} 개")
        print("이관 작업이 성공적으로 종료되었습니다.")
        
    except Exception as ex:
        print(f"❌ 이관 중 예외 발생: {ex}")
    finally:
        kavita_conn.close()
        general_conn.close()

def run_bookoasis_to_bookoasis():
    print("\n==================================================")
    print(" 🛠️  [Step 2] BookOasis ➡️ BookOasis 경로 교체 설정")
    print("==================================================")
    
    # 1. BookOasis 루트 경로 획득
    default_oasis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\', '/')
    oasis_root_input = input(f"BookOasis의 루트 경로를 입력하세요 ({default_oasis_root})\n맞으면 엔터, 수정하려면 경로 입력\n> ").strip()
    oasis_root = oasis_root_input if oasis_root_input else default_oasis_root
    
    db_dir = os.path.join(oasis_root, 'db')
    covers_dir = os.path.join(oasis_root, 'covers')
    
    target_dbs = []
    for db_name in ['media_general.db', 'media_adult.db']:
        db_path = os.path.join(db_dir, db_name)
        if os.path.exists(db_path):
            target_dbs.append(db_path)
            
    if not target_dbs:
        print("❌ 에러: 변경할 BookOasis 데이터베이스 파일이 존재하지 않습니다.")
        return

    # 2. 경로 교체 규칙 획득
    old_prefix = input("교체 대상 기존 경로 프리픽스(Old Prefix)를 입력하세요:\n예: /home/az001a/Script/media_server\n> ").strip()
    new_prefix = input("신규 경로 프리픽스(New Prefix)를 입력하세요:\n예: C:/project/media_server\n> ").strip()
    
    if not old_prefix or not new_prefix:
        print("❌ 에러: 교체할 이전/이후 경로는 비워둘 수 없습니다.")
        return

    print("\n==================================================")
    print(" 🚀 [Step 3] 경로 교체 및 커버 해시 리네이밍 실행")
    print("==================================================")
    
    for db_path in target_dbs:
        db_name = os.path.basename(db_path)
        print(f"\n[*] 데이터베이스 처리 중: {db_name}")
        
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        try:
            # 1. 라이브러리 물리 경로 갱신
            cursor.execute("SELECT id, name, physical_path FROM libraries")
            libraries = cursor.fetchall()
            for lib in libraries:
                if lib['physical_path'] and old_prefix in lib['physical_path']:
                    updated_path = lib['physical_path'].replace(old_prefix, new_prefix)
                    cursor.execute("UPDATE libraries SET physical_path = ? WHERE id = ?", (updated_path, lib['id']))
                    print(f"  └ 라이브러리 [{lib['name']}] 경로 변경: {lib['physical_path']} -> {updated_path}")
            conn.commit()
            
            # 2. 도서 목록 조회 및 리네임 작업
            cursor.execute("SELECT id, file_path, cover_image, library_id FROM books")
            books = cursor.fetchall()
            
            updated_books_count = 0
            renamed_covers_count = 0
            
            for b in books:
                file_path = b['file_path']
                if not file_path or old_prefix not in file_path:
                    continue
                    
                # 신규 파일 경로 구함
                new_file_path = file_path.replace(old_prefix, new_prefix)
                
                # 커버 이미지 해시 리네임 연계 처리
                cover_image = b['cover_image']
                new_cover_image = cover_image
                
                if cover_image and not cover_image.startswith('series_'):
                    # 기존 해시 파일명
                    old_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
                    # 새 해시 파일명
                    new_hash = hashlib.md5(new_file_path.encode('utf-8')).hexdigest()
                    
                    old_cover_filename = f"book_{old_hash}.webp"
                    new_cover_filename = f"book_{new_hash}.webp"
                    
                    lib_id = b['library_id']
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
                            print(f"  └ [물리 커버 리네임 실패] {old_cover_filename} -> {new_cover_filename}: {e}")
                            
                # DB 데이터 업데이트 쿼리 반영
                cursor.execute(
                    "UPDATE books SET file_path = ?, cover_image = ? WHERE id = ?",
                    (new_file_path, new_cover_image, b['id'])
                )
                updated_books_count += 1
                
            conn.commit()
            print(f"  [+] 완료: {updated_books_count}권의 도서 경로 수정 및 {renamed_covers_count}개의 표지 해시 파일 리네이밍 성공.")
            
        except Exception as e:
            print(f"❌ {db_name} 처리 중 에러 발생: {e}")
        finally:
            conn.close()
            
    print("\n==================================================")
    print(" ✨ 경로 및 커버 교체 작업이 성공적으로 종결되었습니다.")
    print("==================================================")

def main():
    print("==================================================")
    print(" 📊 BookOasis 데이터 이관 및 관리 시스템 (v1.0)")
    print("==================================================")
    print(" [Step 1] 마이그레이션 모드를 선택하세요:")
    print("  1. Kavita ➡️ BookOasis 이관")
    print("  2. BookOasis ➡️ BookOasis (서버 기기 이동/경로 교체)")
    
    choice = input("\n>> 원하는 메뉴 번호를 입력 후 엔터 (기본값: 1)\n> ").strip()
    if not choice:
        choice = '1'
        
    if choice == '1':
        run_kavita_to_bookoasis()
    elif choice == '2':
        run_bookoasis_to_bookoasis()
    else:
        print("❌ 잘못된 메뉴 선택입니다. 종료합니다.")

if __name__ == '__main__':
    main()
