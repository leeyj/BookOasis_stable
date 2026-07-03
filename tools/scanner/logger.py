# -*- coding: utf-8 -*-
import os
import builtins
import datetime
from contextlib import contextmanager
import database

@contextmanager
def scanner_print_control(db_path):
    original_print = builtins.print
    write_log = True
    conn = None
    try:
        db_type = 'adult' if 'adult' in os.path.basename(db_path) else 'general'
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'SCANNER_WRITE_LOG'")
        row = cursor.fetchone()
        if row:
            value = str(row['value']).strip()
            if value == '0':
                write_log = False
    except Exception:
        pass
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    if not write_log:
        builtins.print = lambda *args, **kwargs: None
    else:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, 'scanner.log')
        
        def custom_print(*args, **kwargs):
            try:
                sep = kwargs.get('sep', ' ')
                end = kwargs.get('end', '\n')
                message = sep.join(map(str, args)) + end
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                formatted_message = f"[{timestamp}] {message}"
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    f.write(formatted_message)
            except Exception:
                pass
        builtins.print = custom_print
        
    try:
        yield
    finally:
        builtins.print = original_print

def scanner_print_control_decorator(func):
    def wrapper(db_path, *args, **kwargs):
        ctx = scanner_print_control(db_path)
        ctx.__enter__()
        try:
            return func(db_path, *args, **kwargs)
        finally:
            ctx.__exit__(None, None, None)
    return wrapper
