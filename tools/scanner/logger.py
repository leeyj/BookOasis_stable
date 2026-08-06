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
        from repositories.settings_repository import SettingsRepository
        val = SettingsRepository.get_value(db_type, 'SCANNER_WRITE_LOG')
        if val is not None and str(val).strip() == '0':
            write_log = False
    except Exception:
        pass

    if not write_log:
        builtins.print = lambda *args, **kwargs: None
    else:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, 'scanner.log')
        from utils.logger import ZipRotatingLogger
        # 10MB 기준 자동 zip 회전 아카이빙 로거 생성
        zip_logger = ZipRotatingLogger(log_file_path, 10 * 1024 * 1024)
        
        def custom_print(*args, **kwargs):
            try:
                sep = kwargs.get('sep', ' ')
                end = kwargs.get('end', '\n')
                message = sep.join(map(str, args)) + end
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if not message.strip().startswith('[202'):
                    formatted_message = f"[{timestamp}] {message}"
                else:
                    formatted_message = message
                zip_logger.write(formatted_message)
                original_print(formatted_message, end='', flush=True)
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
