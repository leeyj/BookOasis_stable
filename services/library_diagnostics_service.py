# -*- coding: utf-8 -*-
"""
library_diagnostics_service.py – MCP 서버(tools/mcp_server.py)가 사용하는 서재 데이터품질
진단 전담 서비스. 리포지토리의 진단 쿼리를 얇게 감싸고 db_type 검증만 담당한다.
"""

_VALID_DB_TYPES = ('general', 'adult', 'audiobook')


def _validate_db_type(db_type):
    db_type = (db_type or 'general').strip().lower()
    if db_type not in _VALID_DB_TYPES:
        raise ValueError(f"지원하지 않는 db_type입니다: {db_type} (허용값: {', '.join(_VALID_DB_TYPES)})")
    return db_type


class LibraryDiagnosticsService:
    @staticmethod
    def get_stats(db_type):
        """서재 전체 및 카테고리별 시리즈/도서 권수 통계"""
        from services.series_service import SeriesService
        db_type = _validate_db_type(db_type)
        totals = SeriesService.get_books_totals(db_type, 'all')
        per_library = SeriesService.get_library_totals_bulk(db_type)
        return {
            'db_type': db_type,
            'total_series_count': totals.get('total_series_count', 0),
            'total_book_count': totals.get('total_book_count', 0),
            'per_library': per_library,
        }

    @staticmethod
    def find_missing_cover(db_type, library_id=None, limit=50, offset=0):
        from repositories.book_repository import BookRepository
        db_type = _validate_db_type(db_type)
        return BookRepository.find_missing_cover(db_type, library_id=library_id, limit=limit, offset=offset)

    @staticmethod
    def find_missing_genre_and_tags(db_type, library_id=None, limit=50, offset=0):
        from repositories.book_repository import BookRepository
        db_type = _validate_db_type(db_type)
        return BookRepository.find_missing_genre_and_tags(db_type, library_id=library_id, limit=limit, offset=offset)

    @staticmethod
    def list_series_table(db_type, library_id=None, missing='', sort=None, direction=None, search='', page=1, limit=50):
        """관리자 테이블 뷰와 같은 시리즈 표 (정렬·빈 값 필터). 요약이 준비 안 됐으면 ValueError."""
        from services.series_table_service import SeriesTableService, SummaryNotReady
        try:
            return SeriesTableService.list_rows(
                db_type, library_id=library_id, page=page, limit=limit, sort=sort, direction=direction,
                missing=missing, search=search)
        except SummaryNotReady:
            raise ValueError('시리즈 요약을 만드는 중입니다. 잠시 후 다시 시도해 주세요.')

    @staticmethod
    def find_missing_offsets(db_type, library_id=None, limit=50, offset=0):
        from repositories.book_repository import BookRepository
        db_type = _validate_db_type(db_type)
        return BookRepository.find_missing_offsets(db_type, library_id=library_id, limit=limit, offset=offset)

    @staticmethod
    def find_duplicate_series(db_type):
        from repositories.book_repository import BookRepository
        db_type = _validate_db_type(db_type)
        return BookRepository.find_duplicate_series_across_libraries(db_type)
