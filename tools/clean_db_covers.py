# -*- coding: utf-8 -*-
import os
import sqlite3
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_GENERAL_PATH = os.path.join(BASE_DIR, 'db', 'media_general.db')
DB_ADULT_PATH = os.path.join(BASE_DIR, 'db', 'media_adult.db')

def migrate_db(db_path):
    if not os.path.exists(db_path):
        print(f"[-] DB 파일 없음: {db_path}")
        return
        
    print(f"[*] 마이그레이션 시작: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # cover_image 가 book_ 으로 시작하는 책 목록 조회
    cursor.execute("SELECT id, file_path, cover_image FROM books WHERE cover_image LIKE 'book_%.png'")
    rows = cursor.fetchall()
    
    print(f"[*] 총 검사 대상 도서 수: {len(rows)}권")
    
    update_count = 0
    for r in rows:
        book_id = r['id']
        file_path = r['file_path']
        cover_image = r['cover_image']
        
        if not file_path:
            continue
            
        filename = os.path.basename(file_path)
        
        # 1. 파일명 기반 MD5 해시 재현
        legacy_hash = hashlib.md5(filename.encode('utf-8')).hexdigest()
        legacy_cover_name = f"book_{legacy_hash}.png"
        
        # 2. 만약 현재 DB에 저장된 값이 파일명 기반 구형 해시라면 마이그레이션 진행
        if cover_image == legacy_cover_name:
            # 전체 경로 기반 신형 고유 해시 생성
            new_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
            new_cover_name = f"book_{new_hash}.png"
            
            cursor.execute("UPDATE books SET cover_image = ? WHERE id = ?", (new_cover_name, book_id))
            update_count += 1
            
    conn.commit()
    conn.close()
    print(f"[+] 마이그레이션 완료: {db_path} - 총 {update_count}권 정화 완료")

if __name__ == '__main__':
    migrate_db(DB_GENERAL_PATH)
    migrate_db(DB_ADULT_PATH)
