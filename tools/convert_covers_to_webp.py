# -*- coding: utf-8 -*-
"""
convert_covers_to_webp.py
기존 covers 디렉터리에 존재하는 JPG, PNG 등의 표지 이미지들을 WebP 포맷으로 일괄 변환하고,
SQLite 데이터베이스(books, series 테이블) 내의 cover_image 컬럼을 새 webp 파일명으로 갱신하는 일회성 마이그레이션 툴입니다.
"""

import os
import sqlite3
import hashlib
from PIL import Image

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COVERS_DIR = os.path.join(MEDIA_SERVER_DIR, 'covers')
DB_DIR = os.path.join(MEDIA_SERVER_DIR, 'db')

def get_db_paths():
    """db/ 폴더 내 모든 sqlite db 파일 경로 반환"""
    db_files = []
    if os.path.exists(DB_DIR):
        for f in os.listdir(DB_DIR):
            if f.endswith('.db'):
                db_files.append(os.path.join(DB_DIR, f))
    return db_files

def convert_image_to_webp(src_path, dest_path, quality=80):
    """일반 이미지를 WebP로 인코딩하여 저장"""
    try:
        with Image.open(src_path) as img:
            # WebP 저장을 위해 RGBA 혹은 RGB 모드 유지
            img.save(dest_path, "WEBP", quality=quality)
        return True
    except Exception as e:
        print(f"[-] 이미지 변환 실패 ({src_path} -> {dest_path}): {e}")
        return False

def migrate_db(db_path):
    """특정 데이터베이스 파일 내 표지 파일 갱신 및 파일 변환"""
    print(f"\n[*] 데이터베이스 마이그레이션 시작: {os.path.basename(db_path)}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1) books 테이블 마이그레이션
    cursor.execute("SELECT id, cover_image FROM books WHERE cover_image IS NOT NULL AND cover_image != ''")
    books = cursor.fetchall()
    
    converted_books_count = 0
    for book in books:
        book_id = book['id']
        old_cover = book['cover_image']
        
        # 이미 webp인 경우 스킵
        if old_cover.lower().endswith('.webp'):
            continue
            
        old_cover_path = os.path.join(COVERS_DIR, old_cover)
        
        # 새 파일명 및 경로 정의
        base_name, _ = os.path.splitext(old_cover)
        new_cover = base_name + ".webp"
        new_cover_path = os.path.join(COVERS_DIR, new_cover)
        
        if os.path.exists(old_cover_path):
            # 대상 디렉토리 보장
            os.makedirs(os.path.dirname(new_cover_path), exist_ok=True)
            
            # WebP 변환
            if convert_image_to_webp(old_cover_path, new_cover_path):
                # DB 업데이트
                cursor.execute("UPDATE books SET cover_image = ? WHERE id = ?", (new_cover, book_id))
                # 구형 파일 삭제
                try:
                    os.remove(old_cover_path)
                except Exception as e:
                    print(f"[!] 원본 파일 삭제 실패 ({old_cover_path}): {e}")
                converted_books_count += 1
        else:
            # 파일이 유실되었으나 확장자만이라도 일치시켜주기 위해 DB 업데이트 수행
            cursor.execute("UPDATE books SET cover_image = ? WHERE id = ?", (new_cover, book_id))
            
    # 2) series 테이블 마이그레이션
    # 이 프로젝트 DB의 series 테이블 명세(cover_image 등) 유무 점검
    try:
        cursor.execute("SELECT id, cover_image FROM series WHERE cover_image IS NOT NULL AND cover_image != ''")
        series_list = cursor.fetchall()
        
        converted_series_count = 0
        for series in series_list:
            series_id = series['id']
            old_cover = series['cover_image']
            
            if old_cover.lower().endswith('.webp'):
                continue
                
            old_cover_path = os.path.join(COVERS_DIR, old_cover)
            base_name, _ = os.path.splitext(old_cover)
            new_cover = base_name + ".webp"
            new_cover_path = os.path.join(COVERS_DIR, new_cover)
            
            if os.path.exists(old_cover_path):
                os.makedirs(os.path.dirname(new_cover_path), exist_ok=True)
                if convert_image_to_webp(old_cover_path, new_cover_path):
                    cursor.execute("UPDATE series SET cover_image = ? WHERE id = ?", (new_cover, series_id))
                    try:
                        os.remove(old_cover_path)
                    except Exception as e:
                        pass
                    converted_series_count += 1
            else:
                cursor.execute("UPDATE series SET cover_image = ? WHERE id = ?", (new_cover, series_id))
        print(f"[+] series 테이블 변환 완료: {converted_series_count}건")
    except sqlite3.OperationalError:
        # series 테이블에 cover_image 컬럼이 없거나 테이블이 없는 경우 예외 스킵
        print("[*] series 테이블이 존재하지 않거나 cover_image 컬럼이 없어 스킵합니다.")
        
    conn.commit()
    conn.close()
    print(f"[+] books 테이블 변환 완료: {converted_books_count}건")

def main():
    print("=== BookOasis 표지 이미지 WebP 일괄 변환 마이그레이션 툴 ===")
    
    # Pillow 라이브러리 검증
    try:
        from PIL import Image
    except ImportError:
        print("[-] Pillow 라이브러리가 설치되어 있지 않습니다. 'pip install pillow'를 먼저 실행해 주세요.")
        return

    db_paths = get_db_paths()
    if not db_paths:
        print("[-] 마이그레이션할 데이터베이스(*.db) 파일을 db/ 디렉터리에서 찾지 못했습니다.")
        return
        
    for db_path in db_paths:
        migrate_db(db_path)
        
    print("\n[+] 모든 마이그레이션 작업이 안전하게 완료되었습니다!")

if __name__ == '__main__':
    main()
