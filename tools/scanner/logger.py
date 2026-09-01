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
        from repositories.settings_repository import SettingsRepository
        val = SettingsRepository.get_value('SCANNER_WRITE_LOG')
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
        
        # 스캐너 상세 로그를 scanner.log 전용 로거로 분리
        # scanner.log에만 기록 – sys.stdout(=media_server.log)으로는 전달하지 않음
        # 단, 고수준 요약 태그([Scanner-Trigger], [Queue], [Worker] 등)는 media_server.log에도 기록
        SUMMARY_TAGS = (
            '[Scanner-Trigger]', '[Scanner-VFS]', '[Queue]',
            '[Worker-Acquire]', '[Worker]', '[Scanner-Progress]',
            '[Scheduler]', '[Scheduler ERROR]',
        )

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
                # scanner.log에 항상 기록
                zip_logger.write(formatted_message)
                # media_server.log(sys.stdout)에는 고수준 요약 태그만 전달
                if any(tag in formatted_message for tag in SUMMARY_TAGS):
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
