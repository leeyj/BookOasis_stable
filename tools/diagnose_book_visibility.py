# -*- coding: utf-8 -*-
import argparse
import os
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATHS = {
    'general': PROJECT_ROOT / 'db' / 'media_general.db',
    'adult': PROJECT_ROOT / 'db' / 'media_adult.db',
}


def open_read_only(db_path):
    absolute_path = Path(db_path).resolve()
    if not absolute_path.is_file():
        raise FileNotFoundError(f'DB 파일을 찾을 수 없습니다: {absolute_path}')
    connection = sqlite3.connect(f'{absolute_path.as_uri()}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def comparison_dir(file_path, file_format):
    normalized = str(file_path or '').replace('\\', '/')
    if not normalized:
        return ''
    parent = os.path.dirname(normalized)
    if str(file_format or '').lower() == 'imgdir' and normalized.endswith('/__folder__.imgdir'):
        return os.path.dirname(parent)
    return parent


def find_user(connection, user_id):
    if user_id is None:
        return None
    return connection.execute(
        'SELECT id, username, role FROM users WHERE id = ?',
        (user_id,),
    ).fetchone()


def find_books(connection, query):
    like_query = f'%{query}%'
    return connection.execute(
        """
        SELECT b.id, b.title, b.series_name, b.author, b.library_id,
               b.file_path, b.file_format, COALESCE(b.is_deleted, 0) AS is_deleted,
               l.name AS library_name
        FROM books b
        LEFT JOIN libraries l ON l.id = b.library_id
        WHERE COALESCE(b.title, '') LIKE ?
           OR COALESCE(b.series_name, '') LIKE ?
           OR COALESCE(b.author, '') LIKE ?
           OR COALESCE(b.file_path, '') LIKE ?
        ORDER BY b.library_id, b.series_name, b.id
        """,
        (like_query, like_query, like_query, like_query),
    ).fetchall()


def has_permission(connection, user_id, role, library_id):
    if user_id is None or role == 'admin':
        return True
    row = connection.execute(
        """
        SELECT has_access
        FROM user_category_permissions
        WHERE user_id = ? AND library_id = ?
        """,
        (user_id, library_id),
    ).fetchone()
    return bool(row and row['has_access'] == 1)


def diagnose(db_path, query, user_id=None, library_id=None):
    connection = open_read_only(db_path)
    try:
        user = find_user(connection, user_id)
        if user_id is not None and user is None:
            print(f'[오류] users 테이블에서 user_id={user_id}를 찾지 못했습니다.')
            return 2

        role = user['role'] if user else None
        rows = find_books(connection, query)

        print('=' * 88)
        print('BookOasis 도서 노출 진단 (읽기 전용)')
        print(f'DB       : {Path(db_path).resolve()}')
        print(f'검색어   : {query}')
        if user:
            print(f'사용자   : {user["username"]} (id={user["id"]}, role={role})')
        else:
            print('사용자   : 관리자 기준(권한 필터 없음)')
        print(f'카테고리 : {library_id if library_id is not None else "전체"}')
        print('=' * 88)

        if not rows:
            print('[결과] title/series_name/author/file_path 어디에도 검색어가 없습니다.')
            return 1

        visible_count = 0
        for row in rows:
            reasons = []
            if row['is_deleted'] != 0:
                reasons.append(f'is_deleted={row["is_deleted"]}')
            if library_id is not None and row['library_id'] != library_id:
                reasons.append(f'선택 카테고리 불일치({row["library_id"]} != {library_id})')
            if not has_permission(connection, user_id, role, row['library_id']):
                reasons.append('사용자 카테고리 권한 없음')

            visible = not reasons
            if visible:
                visible_count += 1
            series_name = row['series_name'] or '기타 단행본'
            group_dir = comparison_dir(row['file_path'], row['file_format'])

            print(f'[{"노출" if visible else "제외"}] book_id={row["id"]}')
            print(f'  title       : {row["title"]}')
            print(f'  series_name : {row["series_name"]}')
            print(f'  library     : {row["library_id"]} / {row["library_name"]}')
            print(f'  file_path   : {row["file_path"]}')
            print(f'  group_key   : ({row["library_id"]}, {series_name!r}, {group_dir!r})')
            if reasons:
                print(f'  제외 원인   : {", ".join(reasons)}')
            elif query.lower() not in str(series_name).lower() and query.lower() in str(row['title'] or '').lower():
                print('  참고        : 제목만 일치합니다. 구버전 검색은 이 행을 찾지 못합니다.')
            print('-' * 88)

        print(f'[요약] DB 검색 {len(rows)}권 / 지정 사용자 목록 노출 {visible_count}권')
        if visible_count > 0:
            print('[판정] 서버 목록 SQL을 통과합니다. 배포 버전 또는 브라우저의 선로드 목록을 확인하세요.')
            return 0
        print('[판정] 모든 행이 서버 목록 SQL 조건에서 제외됩니다. 위 제외 원인을 확인하세요.')
        return 1
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description='특정 도서가 사용자 목록 API 조건을 통과하는지 읽기 전용으로 진단합니다.'
    )
    parser.add_argument('query', help='도서 제목, 시리즈명, 작가 또는 경로 검색어')
    parser.add_argument('--db', choices=('general', 'adult'), default='general', help='DB 종류')
    parser.add_argument('--db-path', help='기본 경로 대신 사용할 SQLite DB 파일')
    parser.add_argument('--user-id', type=int, help='비관리자 권한 필터를 재현할 사용자 ID')
    parser.add_argument('--library-id', type=int, help='특정 카테고리 선택 조건을 재현할 library ID')
    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else DEFAULT_DB_PATHS[args.db]
    try:
        return diagnose(
            db_path,
            args.query.strip(),
            user_id=args.user_id,
            library_id=args.library_id,
        )
    except (sqlite3.Error, OSError) as error:
        print(f'[오류] 진단 실패: {error}')
        return 2


if __name__ == '__main__':
    sys.exit(main())