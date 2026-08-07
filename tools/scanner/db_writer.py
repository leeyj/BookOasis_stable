# -*- coding: utf-8 -*-
"""
db_writer.py – DB 엔진(SQLite / MariaDB)에 따른 스캐너 DB 업서트/배치 동적 라우터 모듈
"""
import os
from tools.scanner import db_writer_sqlite
from tools.scanner import db_writer_mariadb

def _is_mariadb():
    engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
    return engine in ('mariadb', 'mysql')

def get_writer():
    return db_writer_mariadb if _is_mariadb() else db_writer_sqlite

def update_book_metadata(*args, **kwargs):
    return get_writer().update_book_metadata(*args, **kwargs)

def insert_new_book_v2(*args, **kwargs):
    return get_writer().insert_new_book_v2(*args, **kwargs)

def save_book_offsets(*args, **kwargs):
    return get_writer().save_book_offsets(*args, **kwargs)

def bulk_update_books(*args, **kwargs):
    return get_writer().bulk_update_books(*args, **kwargs)

def bulk_insert_books(*args, **kwargs):
    return get_writer().bulk_insert_books(*args, **kwargs)

def bulk_save_book_offsets(*args, **kwargs):
    return get_writer().bulk_save_book_offsets(*args, **kwargs)
