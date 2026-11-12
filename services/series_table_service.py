# -*- coding: utf-8 -*-
"""관리자 테이블 뷰: 시리즈를 표로 보고(정렬·빈 값 필터), 셀에서 메타를 고치고, CSV로 내보낸다.

대상은 일반/성인 도서뿐이다 (오디오북·영상은 표와 잠금 구조가 다르다).
"""
import csv
import io

from repositories.series_repository import SeriesRepository
from repositories.series_table_query import COLUMNS, EDITABLE_KEYS
from services import series_metadata_patch
from utils.cover_helper import get_cover_image_with_t

SUPPORTED_DB_TYPES = ('general', 'adult')
MAX_PAGE_SIZE = 200
EXPORT_CHUNK = 2000
# CSV 열 순서. 표지는 뺀다(경로뿐이라 쓸모가 없다)
EXPORT_COLUMNS = (
    'library_id', 'series_name', 'series_alias', 'author', 'publisher', 'isbn', 'genre', 'tags',
    'books_lv', 'publication_status', 'summary', 'score', 'book_count', 'file_format', 'latest_added', 'metadata_locked',
)
_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def _clean_value(field, value):
    """셀 입력 정리. 한 줄 필드는 공백을 한 칸으로, 설명(summary)은 줄바꿈을 살리고 줄 끝 공백과 3줄 이상 빈 줄만 줄인다."""
    text = str(value if value is not None else '')
    if field != 'summary':
        return ' '.join(text.split())
    lines = [line.rstrip() for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    cleaned = '\n'.join(lines).strip()
    while '\n\n\n' in cleaned:
        cleaned = cleaned.replace('\n\n\n', '\n\n')
    return cleaned


class SummaryNotReady(Exception):
    """시리즈 요약(series_summary)이 아직 만들어지는 중."""


def validate_db_type(db_type):
    db_type = str(db_type or 'general').strip().lower()
    if db_type not in SUPPORTED_DB_TYPES:
        raise ValueError(f"테이블 뷰는 도서(general/adult)만 지원합니다: {db_type}")
    return db_type


def _shape_row(row):
    series_name = row.get('series_name') or ''
    return {
        'representative_book_id': row.get('representative_book_id'),
        'library_id': row.get('library_id'),
        'series_name': series_name,
        'series_alias': row.get('series_alias') or '',
        'author': row.get('author') or '',
        'publisher': row.get('publisher') or '',
        'isbn': row.get('isbn') or '',
        'genre': row.get('genre') or '',
        'tags': row.get('tags') or '',
        'books_lv': row.get('books_lv') or '',
        'publication_status': str(row.get('publication_status') or ''),
        'summary': row.get('summary') or '',
        'score': row.get('score'),
        'book_count': int(row.get('book_count') or 0),
        'file_format': row.get('file_format') or '',
        'latest_added': str(row.get('latest_added') or ''),
        'metadata_locked': 1 if int(row.get('metadata_locked') or 0) == 1 else 0,
        'cover_image': get_cover_image_with_t(row.get('cover_image'), row.get('cover_updated_at')),
        # 저장은 series_name 일치로 시리즈 전체 권을 갱신한다 - 이름이 빈 행(기타 단행본)을 고치면
        # 시리즈 없는 책 전부가 한꺼번에 바뀌므로 막는다 (상세 화면 수정도 빈 이름은 거부한다)
        'editable': bool(series_name.strip()),
    }


class SeriesTableService:
    @staticmethod
    def list_rows(db_type, library_id=None, page=1, limit=100, sort=None, direction=None, missing=None,
                  search='', genres=None, tags=None, filter_mode='and'):
        """반환: {'rows', 'total'(1쪽에서만, 그 외 None), 'has_more', 'page', 'limit'}"""
        db_type = validate_db_type(db_type)
        page = max(1, int(page or 1))
        limit = max(1, min(MAX_PAGE_SIZE, int(limit or 100)))
        result = SeriesRepository.fetch_series_table(
            db_type, library_id=library_id, sort=sort, direction=direction, missing=missing, search=search,
            genres=genres, tags=tags, filter_mode=filter_mode,
            limit=limit + 1, offset=(page - 1) * limit,
            # 건수는 조건이 같으면 변하지 않으니 첫 쪽에서만 센다 (홈 6.5만 시리즈 실측: 필터 건수 ~90ms)
            with_total=(page == 1),
        )
        if result is None:
            raise SummaryNotReady()
        rows = result['rows']
        return {
            'rows': [_shape_row(row) for row in rows[:limit]],
            'total': result['total'],
            'has_more': len(rows) > limit,
            'page': page,
            'limit': limit,
        }

    @staticmethod
    def save_cell(db_type, series_name, field, value, library_id=None):
        """셀 하나 저장. 반환: {'changed': {...}, 'value': 저장된 값}. 입력이 잘못되면 ValueError."""
        db_type = validate_db_type(db_type)
        series_name = str(series_name or '').strip()
        if not series_name:
            raise ValueError('시리즈명이 없는 행은 여기서 고칠 수 없습니다.')
        field = str(field or '').strip()
        if field not in EDITABLE_KEYS:
            raise ValueError(f"고칠 수 없는 필드입니다: {field}")
        value = _clean_value(field, value)
        fields = {field: value}
        series_metadata_patch.validate_fields(fields, strict_values=True)
        changed, success, message = series_metadata_patch.apply_fields(
            db_type, series_name, library_id if library_id not in (None, '') else 'all', fields)
        if not success:
            raise RuntimeError(message or '저장하지 못했습니다.')
        return {'changed': changed, 'value': value}

    @staticmethod
    def normalize_export_columns(columns):
        if isinstance(columns, str):
            columns = columns.split(',')
        picked = [c for c in EXPORT_COLUMNS if c in {str(v or '').strip() for v in (columns or [])}]
        # 시리즈명은 행을 식별하는 값이라 항상 넣는다
        if picked and 'series_name' not in picked:
            picked.insert(0, 'series_name')
        return picked or list(EXPORT_COLUMNS)

    @staticmethod
    def iter_csv(db_type, columns=None, **filters):
        """필터에 걸린 전체 행을 CSV 조각(str)으로 낸다. 첫 조각은 BOM + 머리글(Excel 한글 깨짐 방지)."""
        db_type = validate_db_type(db_type)
        columns = SeriesTableService.normalize_export_columns(columns)
        # 스트리밍 응답은 첫 조각을 꺼내기 전까지 예외가 안 나므로, 요약 준비 여부는 여기서 먼저 확인한다
        first = SeriesRepository.fetch_series_table(db_type, limit=EXPORT_CHUNK, offset=0, with_total=False, **filters)
        if first is None:
            raise SummaryNotReady()

        def generate():
            yield '﻿' + _csv_line(columns)
            chunk, offset = first['rows'], 0
            while chunk:
                for row in chunk:
                    shaped = _shape_row(row)
                    yield _csv_line([_csv_cell(shaped.get(col)) for col in columns])
                if len(chunk) < EXPORT_CHUNK:
                    break
                offset += EXPORT_CHUNK
                result = SeriesRepository.fetch_series_table(
                    db_type, limit=EXPORT_CHUNK, offset=offset, with_total=False, **filters)
                chunk = result['rows'] if result else []

        return generate()


def _csv_cell(value):
    """수식 실행 방지: = + - @ 로 시작하는 문자열은 Excel이 수식으로 읽으므로 앞에 '를 붙인다."""
    if value is None:
        return ''
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _csv_line(cells):
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator='\r\n').writerow(cells)
    return buffer.getvalue()


assert set(EDITABLE_KEYS) <= set(series_metadata_patch.ALLOWED_FIELDS)
assert set(EXPORT_COLUMNS) - {'library_id'} <= set(COLUMNS)
