# -*- coding: utf-8 -*-
import sys
import os
import datetime
import zipfile
import re

TIMESTAMP_REGEX = re.compile(r'^(?:\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]|\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')

DEFAULT_ARCHIVE_MAX_FILES = 10
DEFAULT_ARCHIVE_MAX_MB = 200

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()


def debug(*args, **kwargs):
    """LOG_LEVEL=DEBUG일 때만 출력되는 상세 로그. 운영 컨테이너에서는 기본적으로 무음."""
    if LOG_LEVEL == 'DEBUG':
        print('[DEBUG]', *args, **kwargs)


def _read_nonnegative_int_env(name, default):
    try:
        return max(0, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default

class ZipRotatingLogger:
    def __init__(self, filepath, max_bytes, archive_max_files=None, archive_max_bytes=None):
        self.filepath = filepath
        self.max_bytes = max_bytes
        self.log_dir = os.path.dirname(filepath)
        self.filename = os.path.basename(filepath)
        self.archive_max_files = (
            _read_nonnegative_int_env('LOG_ARCHIVE_MAX_FILES', DEFAULT_ARCHIVE_MAX_FILES)
            if archive_max_files is None else max(0, int(archive_max_files))
        )
        self.archive_max_bytes = (
            _read_nonnegative_int_env('LOG_ARCHIVE_MAX_MB', DEFAULT_ARCHIVE_MAX_MB) * 1024 * 1024
            if archive_max_bytes is None else max(0, int(archive_max_bytes))
        )
        self._archive_pattern = re.compile(
            rf'^{re.escape(self.filename)}_\d{{8}}_\d{{6}}(?:_\d{{6}})?\.zip$'
        )
        os.makedirs(self.log_dir, exist_ok=True)
        self._current_size = 0
        if os.path.exists(filepath):
            self._current_size = os.path.getsize(filepath)
        self._at_line_start = True
        self._cleanup_archives()

    def _list_archives(self):
        archives = []
        try:
            entries = os.scandir(self.log_dir)
        except OSError:
            return archives

        with entries:
            for entry in entries:
                try:
                    if entry.is_file() and self._archive_pattern.match(entry.name):
                        stat = entry.stat()
                        archives.append((stat.st_mtime, entry.name, entry.path, stat.st_size))
                except OSError:
                    continue
        archives.sort(key=lambda archive: (archive[0], archive[1]))
        return archives

    def _cleanup_archives(self):
        archives = self._list_archives()
        total_bytes = sum(archive[3] for archive in archives)

        while archives and (
            len(archives) > self.archive_max_files
            or total_bytes > self.archive_max_bytes
        ):
            _, _, archive_path, archive_size = archives.pop(0)
            try:
                os.remove(archive_path)
                total_bytes -= archive_size
            except OSError:
                continue

    def _rotate(self):
        if not os.path.exists(self.filepath):
            return
        
        now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_name = f"{self.filename}_{now_str}.zip"
        archive_path = os.path.join(self.log_dir, archive_name)
        
        temp_log = self.filepath + ".tmp"
        try:
            os.rename(self.filepath, temp_log)
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(temp_log, self.filename)
            os.remove(temp_log)
            self._cleanup_archives()
        except Exception:
            pass
        self._current_size = 0

    def write(self, msg):
        if not msg:
            return
        
        try:
            msg_str = str(msg)
        except Exception:
            msg_str = repr(msg)

        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        formatted_parts = []
        lines = msg_str.split('\n')
        for i, line in enumerate(lines):
            is_last = (i == len(lines) - 1)
            if self._at_line_start and line.strip():
                if not TIMESTAMP_REGEX.match(line.strip()):
                    line = f"[{now_str}] {line}"
            formatted_parts.append(line)
            if not is_last:
                formatted_parts.append('\n')
                self._at_line_start = True
            else:
                if line:
                    self._at_line_start = False

        final_msg = "".join(formatted_parts)
        msg_bytes = final_msg.encode('utf-8', errors='replace')
            
        if self._current_size + len(msg_bytes) > self.max_bytes:
            self._rotate()
            
        try:
            with open(self.filepath, 'ab') as f:
                f.write(msg_bytes)
            self._current_size += len(msg_bytes)
        except Exception:
            pass

    def flush(self):
        pass

def print_msg(msg):
    """Timestamped print helper"""
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg_str = str(msg)
    if not TIMESTAMP_REGEX.match(msg_str.strip()):
        print(f"[{now_str}] {msg_str}")
    else:
        print(msg_str)

def setup_rotating_logger():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    LOG_FILE = os.path.join(LOG_DIR, 'media_server.log')

    zip_logger = ZipRotatingLogger(LOG_FILE, 10 * 1024 * 1024)
    sys.stdout = zip_logger
    sys.stderr = zip_logger
