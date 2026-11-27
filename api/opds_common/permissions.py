# -*- coding: utf-8 -*-
"""Book access checks for header-auth feeds (/opds, /opds-epaper), matching the web rules.

Feed requests carry Basic auth or a signed token, not a web session, so the flags that the web reads from the
session (has_download_access, content_rating_max) are read from the users row here.

- category: same rule as the web viewer and /app-opds (utils.permission_clause: a granted row is required)
- download permission: same as api.auth.check_download_permission (downloads only, not page streaming)
- content rating: same as api.auth.check_book_rating_permission (ContentRatingService.can_view_book)
Admins skip all three, as on the web.
"""


def load_user(user_id):
    """users row (general DB) as a dict, or None."""
    if not user_id:
        return None
    from repositories.user_repository import UserRepository
    row = UserRepository.find_by_id('general', int(user_id))
    return dict(row) if row else None


def can_access_category(db_type, book_id, user_id, role):
    from repositories.book_repository import BookRepository
    from utils.permission_clause import build_library_permission_clause
    clause, params = build_library_permission_clause(user_id, role, alias='b')
    return BookRepository.get_book_file_info_with_permission(db_type, int(book_id), clause, params) is not None


def refusal(db_type, book_id, user, need_download=True, check_category=True):
    """user: {'id', 'role', ...}. Returns (reason, message) when access is refused, else None.
    reason 'not_found' means the caller should answer 404 (book hidden by category permission)."""
    if not user:
        return 'not_found', 'not found'
    if user.get('role') == 'admin':
        return None
    row = load_user(user.get('id'))
    if not row:
        return 'not_found', 'not found'
    if check_category and not can_access_category(db_type, book_id, row['id'], row.get('role')):
        return 'not_found', 'not found'
    if need_download and int(row.get('has_download_access') or 0) != 1:
        return 'no_download_access', '이 계정은 다운로드 권한이 없습니다.'
    from services.content_rating_service import ContentRatingService, get_user_content_rating_max
    if db_type in ('general', 'adult') and \
            not ContentRatingService.can_view_book(db_type, book_id, get_user_content_rating_max(row)):
        return 'content_rating', '이 계정의 열람 등급으로는 받을 수 없는 책입니다.'
    return None
