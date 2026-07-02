# -*- coding: utf-8 -*-
import sqlite3
import os

def fix_epub_pages():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_dir = os.path.join(root_dir, 'db')
    
    print(f"[*] DB Directory: {db_dir}")
    
    for db_name in ['media_general.db', 'media_adult.db']:
        db_path = os.path.join(db_dir, db_name)
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("UPDATE books SET total_pages = 100 WHERE file_format = 'epub' AND total_pages = 0")
                updated_count = cur.rowcount
                conn.commit()
                conn.close()
                print(f"[+] '{db_name}' - {updated_count}개의 EPUB 도서 total_pages 값을 100으로 일괄 수정했습니다.")
            except Exception as e:
                print(f"[-] '{db_name}' 업데이트 중 오류 발생: {e}")

if __name__ == "__main__":
    fix_epub_pages()
