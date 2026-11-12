# -*- coding: utf-8 -*-
"""시리즈 메타데이터 부분 수정 - MCP 쓰기 도구와 관리자 테이블 뷰 셀 편집이 같이 쓴다.

전달한 필드만 바꾸고 나머지는 현재 값을 유지한다. 실제 저장은 상세 화면 수정과 같은
BookDetailService.update_media_detail()을 타므로 캐시 무효화·자동 잠금(metadata_locked=1)이 똑같이 일어난다.
"""
import re

ALLOWED_FIELDS = ('author', 'isbn', 'publisher', 'summary', 'link', 'genre', 'tags', 'series_alias', 'books_lv', 'publication_status')
PUBLICATION_STATUS_VALUES = ('0', '1', '2')  # 연재 / 휴재 / 완결


def validate_fields(fields, strict_values=False):
    """허용 필드·값 검증. 문제가 있으면 ValueError.

    방어심층화: 이 필드들은 프론트가 이스케이프 없이 innerHTML로 그리던 저장형 XSS 싱크였다(렌더링 쪽은
    따로 고쳤다). 자유 텍스트를 넣을 수 있는 쓰기 경로라 여기서도 HTML 태그(<, >)는 거부한다.
    strict_values=True면 등급·연재 상태를 정해진 값(또는 빈 값)으로만 받는다 (화면의 선택 상자용)."""
    unknown = [k for k in fields if k not in ALLOWED_FIELDS]
    if unknown:
        raise ValueError(f"허용되지 않는 필드입니다: {', '.join(unknown)} (허용: {', '.join(ALLOWED_FIELDS)})")

    for key, value in fields.items():
        if value is not None and ('<' in str(value) or '>' in str(value)):
            raise ValueError(f"'{key}' 필드에 '<' 또는 '>' 문자를 포함할 수 없습니다 (HTML 태그 삽입 방지).")
    if fields.get('link') is not None and fields['link'] and not re.match(r'^https?://', fields['link'].strip(), re.IGNORECASE):
        raise ValueError("link는 http:// 또는 https://로 시작해야 합니다.")

    if strict_values:
        from services.content_rating_service import ALLOWED_BOOKS_LV_VALUES
        books_lv = fields.get('books_lv')
        if books_lv and books_lv not in ALLOWED_BOOKS_LV_VALUES:
            raise ValueError(f"허용되지 않는 등급 값입니다: {books_lv}")
        status = fields.get('publication_status')
        if status and str(status) not in PUBLICATION_STATUS_VALUES:
            raise ValueError(f"허용되지 않는 연재 상태 값입니다: {status}")


def apply_fields(db_type, series_name, library_id, fields):
    """시리즈 하나에 값을 병합·적용한다. 반환: (바뀐 필드 {이름: {before, after}}, 성공 여부, 메시지)"""
    from services.book_detail_service import BookDetailService
    from repositories.book_repository import BookRepository
    # 현재 값은 DB 원본으로 읽는다. 예전엔 화면용 get_media_detail()의 meta를 썼는데, 그건 빈 값을
    # 표시용 문구(작가·출판사 '-', 줄거리 '등록된 설명이 없습니다.')로 채워 주므로 다른 필드 하나만 고쳐도
    # 그 문구가 DB에 저장됐다 (빈 값 필터에서도 빠진다).
    current_row = BookRepository.get_series_meta(db_type, series_name, library_id, '', [])
    if not current_row:
        raise ValueError(f"시리즈를 찾을 수 없습니다: {series_name}")
    current_row = dict(current_row)

    before = {k: (current_row.get(k) if current_row.get(k) is not None else '') for k in ALLOWED_FIELDS}
    merged = dict(before)
    merged.update({k: v for k, v in fields.items() if v is not None})

    success, message = BookDetailService.update_media_detail(
        db_type, series_name,
        author=merged['author'], isbn=merged['isbn'], publisher=merged['publisher'],
        summary=merged['summary'], link=merged['link'], genre=merged['genre'], tags=merged['tags'],
        series_alias=merged['series_alias'], books_lv=merged['books_lv'],
        publication_status=merged['publication_status'],
        library_id=library_id if str(library_id or '').strip().isdigit() else None,
    )

    changed = {k: {'before': before[k], 'after': merged[k]} for k in ALLOWED_FIELDS if before[k] != merged[k]}
    return changed, success, message
