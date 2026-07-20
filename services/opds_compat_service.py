# -*- coding: utf-8 -*-
"""Service helpers for App OPDS compatibility endpoints."""

import database

APP_OPDS_SUPPORTED_FORMATS = {'zip', 'cbz'}


def enrich_books_for_app_opds(books_list, db_type: str, is_adult_prefix: bool):
    prefix = '/app-opds-adult' if is_adult_prefix else '/app-opds'
    enriched = []
    for book in books_list or []:
        item = dict(book)
        fmt = (item.get('file_format') or '').lower()
        item['file_format'] = fmt
        item['format'] = fmt

        book_id = item.get('id')
        if fmt in ('zip', 'cbz', 'imgdir'):
            item['read_url'] = f"{prefix}/api/media/stream?db_type={db_type}&book_id={book_id}&page_idx=0"
            item['reader_type'] = 'comic'
        elif fmt == 'txt':
            item['read_url'] = f"{prefix}/api/media/txt?db_type={db_type}&book_id={book_id}"
            item['reader_type'] = 'txt'
        elif fmt in ('epub', 'pdf'):
            item['read_url'] = f"{prefix}/api/media/pdf?db_type={db_type}&book_id={book_id}"
            item['reader_type'] = fmt
        else:
            item['read_url'] = ''
            item['reader_type'] = fmt or 'unknown'

        enriched.append(item)
    return enriched


def get_supported_series_names(db_type: str, series_names):
    clean_names = [name for name in (series_names or []) if name]
    if not clean_names:
        return set()

    from repositories.opds_repository import OpdsRepository
    return OpdsRepository.get_supported_series_names(db_type, clean_names)


def filter_supported_series_for_app_opds(db_type: str, series_list):
    names = [series.get('series_name', '') for series in (series_list or []) if isinstance(series, dict)]
    allowed_names = get_supported_series_names(db_type, names)
    return [series for series in (series_list or []) if series.get('series_name', '') in allowed_names]


def filter_supported_books_for_app_opds(books_list):
    filtered = []
    for book in books_list or []:
        fmt = str((book or {}).get('file_format') or '').lower()
        if fmt in APP_OPDS_SUPPORTED_FORMATS:
            filtered.append(book)
    return filtered
