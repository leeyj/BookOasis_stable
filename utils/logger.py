# -*- coding: utf-8 -*-
import sys
import os
import datetime
import zipfile
import re

TIMESTAMP_REGEX = re.compile(r'^(?:\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]|\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')

class ZipRotatingLogger:
    def __init__(self, filepath, max_bytes):
        self.filepath = filepath
        self.max_bytes = max_bytes
        self.log_dir = os.path.dirname(filepath)
        self.filename = os.path.basename(filepath)
        os.makedirs(self.log_dir, exist_ok=True)
        self._current_size = 0
        if os.path.exists(filepath):
            self._current_size = os.path.getsize(filepath)
        self._at_line_start = True

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
        except Exception as e:
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
