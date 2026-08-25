from repositories.bookmark_repository import BookmarkRepository

VALID_FORMATS = ('epub', 'txt')
MAX_LABEL_LEN = 200

class BookmarkService:
    @staticmethod
    def create_bookmark(db_type, book_id, user_id, format, chapter_idx, percent=0, label=None):
        format = str(format or '').strip().lower()
        if format not in VALID_FORMATS:
            raise ValueError("지원하지 않는 형식입니다 (epub/txt만 가능).")

        try:
            chapter_idx = int(chapter_idx)
        except (TypeError, ValueError):
            raise ValueError("잘못된 위치 정보입니다.")
        if chapter_idx < 0:
            raise ValueError("잘못된 위치 정보입니다.")

        try:
            percent = int(percent)
        except (TypeError, ValueError):
            percent = 0
        percent = max(0, min(100, percent))

        label = str(label or '').strip()[:MAX_LABEL_LEN] or None

        return BookmarkRepository.create_bookmark(db_type, book_id, user_id, format, chapter_idx, percent, label)

    @staticmethod
    def get_book_bookmarks(db_type, book_id, user_id):
        return BookmarkRepository.get_book_bookmarks(db_type, book_id, user_id)

    @staticmethod
    def delete_bookmark(db_type, bookmark_id, user_id):
        return BookmarkRepository.delete_bookmark(db_type, bookmark_id, user_id)
