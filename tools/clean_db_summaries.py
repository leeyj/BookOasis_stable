# -*- coding: utf-8 -*-
import os
import sqlite3
import re
import html

# 현재 파일 위치: media_server/tools/clean_db_summaries.py
# MEDIA_SERVER_DIR: media_server/
MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(MEDIA_SERVER_DIR, 'db')

DB_PATHS = [
    os.path.join(DB_DIR, 'media_general.db'),
    os.path.join(DB_DIR, 'media_adult.db')
]

HTML_TAG_RE = re.compile(r'<[^>]*>')

def clean_html_tags(text):
    if not text:
        return ''
    # HTML 태그 제거
    cleaned = HTML_TAG_RE.sub('', text)
    # HTML 엔티티 복원 (&nbsp; -> 공백 등)
    return html.unescape(cleaned).strip()

def clean_database_summaries():
    print("=== [미디어 서버 독립] 기존 데이터베이스 줄거리 HTML/이미지 태그 일괄 정화 시작 ===")
    
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            print(f"[*] 존재하지 않는 DB 생략: {db_path}")
            continue
            
        print(f"[*] 대상 DB 작업 시작: {os.path.basename(db_path)}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. books 테이블 조회
        cursor.execute("SELECT id, title, summary FROM books WHERE summary IS NOT NULL AND summary != ''")
        books = cursor.fetchall()
        
        updated_count = 0
        for book in books:
            book_id = book['id']
            title = book['title']
            raw_summary = book['summary']
            
            # HTML 태그가 포함되어 있는지 간이 판별
            if '<' in raw_summary and '>' in raw_summary:
                clean_summary = clean_html_tags(raw_summary)
                
                # 정화된 텍스트가 원본과 다르다면 업데이트 수행
                if clean_summary != raw_summary:
                    cursor.execute("UPDATE books SET summary = ? WHERE id = ?", (clean_summary, book_id))
                    updated_count += 1
                    
        conn.commit()
        conn.close()
        print(f"[+] '{os.path.basename(db_path)}' 정화 완료 (총 {updated_count}개 도서 갱신)")

    print("=== 데이터베이스 정화 작업 완료 ===")

if __name__ == '__main__':
    clean_database_summaries()
