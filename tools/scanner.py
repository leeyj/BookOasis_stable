# -*- coding: utf-8 -*-
import os
import sys

# Add project root path to sys.path to prevent package import errors
MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

from tools.scanner.core import (
    scan_library, 
    scan_library_covers_only, 
    run_sync_scanner
)
from tools.scanner.tasks import (
    process_folder_task,
    SUPPORTED_FORMATS
)
from tools.scanner.engine import MAX_SCANNER_THREADS
from tools.scanner.metadata import parse_info_xml, parse_kavita_yaml, is_consonant_folder, clean_html_tags
from tools.scanner.cover import get_series_cover_fallback, extract_cover_from_b64, extract_epub_cover_direct
from tools.scanner.offset import collect_zip_offsets, collect_zip_offsets_data
from tools.scanner.vfs import trigger_vfs_refresh

if __name__ == '__main__':
    run_sync_scanner()
