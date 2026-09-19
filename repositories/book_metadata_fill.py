# -*- coding: utf-8 -*-
"""Shared rules for filling only the empty metadata columns of a book (SQLite and MariaDB)."""

# 파일 내장 메타데이터(tools/scanner/embedded_metadata.py)로 채울 수 있는 books 컬럼 화이트리스트.
FILLABLE_METADATA_COLUMNS = (
    'author', 'cover_artist', 'teams', 'locations', 'characters', 'books_lv',
    'publisher', 'summary', 'release_date', 'genre', 'tags', 'isbn',
)
# 예전 메타데이터 가져오기가 "설명 없음"의 의미로 저장하던 자리표시 문구 - 빈 값과 같게 취급한다.
SUMMARY_PLACEHOLDER = '등록된 설명이 없습니다.'


def sanitize_fill_candidates(fields):
    """화이트리스트 컬럼 중 값이 있는 것만 문자열로 정리해서 반환한다."""
    candidates = {}
    for column in FILLABLE_METADATA_COLUMNS:
        value = (fields or {}).get(column)
        if value is not None and str(value).strip():
            candidates[column] = str(value).strip()
    return candidates


def is_empty_value(column, value):
    text = str(value if value is not None else '').strip()
    return text == '' or (column == 'summary' and text == SUMMARY_PLACEHOLDER)


def empty_guard_sql(column):
    """UPDATE 안에서 "이 컬럼이 아직 비어 있을 때만"을 판정하는 SQL 조건 (column은 화이트리스트 값이어야 한다)."""
    guard = f"COALESCE(TRIM({column}), '') = ''"
    if column == 'summary':
        guard += f" OR TRIM({column}) = '{SUMMARY_PLACEHOLDER}'"
    return guard
