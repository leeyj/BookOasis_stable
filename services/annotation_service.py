from repositories.annotation_repository import AnnotationRepository

VALID_FORMATS = ('epub', 'txt')
MAX_QUOTE_LEN = 2000
MAX_CONTEXT_LEN = 64
MAX_NOTE_LEN = 2000
DEFAULT_COLOR = '#fbbf24'

class AnnotationService:
    @staticmethod
    def create_annotation(db_type, book_id, user_id, format, chapter_idx, start_offset,
                           end_offset, quote, prefix=None, suffix=None, color=None, note=None):
        format = str(format or '').strip().lower()
        if format not in VALID_FORMATS:
            raise ValueError("지원하지 않는 형식입니다 (epub/txt만 가능).")

        try:
            start_offset = int(start_offset)
            end_offset = int(end_offset)
        except (TypeError, ValueError):
            raise ValueError("잘못된 선택 범위입니다.")
        if start_offset < 0 or end_offset < start_offset:
            raise ValueError("잘못된 선택 범위입니다.")

        quote = str(quote or '').strip()
        if not quote:
            raise ValueError("선택된 텍스트가 없습니다.")
        if len(quote) > MAX_QUOTE_LEN:
            quote = quote[:MAX_QUOTE_LEN]

        prefix = str(prefix or '')[:MAX_CONTEXT_LEN] or None
        suffix = str(suffix or '')[:MAX_CONTEXT_LEN] or None

        if format == 'epub':
            try:
                chapter_idx = int(chapter_idx)
            except (TypeError, ValueError):
                raise ValueError("챕터 정보가 없습니다.")
        else:
            chapter_idx = None

        color = str(color or DEFAULT_COLOR).strip() or DEFAULT_COLOR
        note = str(note or '').strip()[:MAX_NOTE_LEN] or None

        return AnnotationRepository.create_annotation(
            db_type, book_id, user_id, format, chapter_idx, start_offset, end_offset,
            quote, prefix, suffix, color, note
        )

    @staticmethod
    def get_book_annotations(db_type, book_id, user_id):
        return AnnotationRepository.get_book_annotations(db_type, book_id, user_id)

    @staticmethod
    def update_annotation(db_type, annotation_id, user_id, color=None, note=None):
        existing = AnnotationRepository.get_annotation_by_id(db_type, annotation_id, user_id)
        if not existing:
            raise ValueError("주석을 찾을 수 없거나 접근 권한이 없습니다.")

        color = str(color or existing.get('color') or DEFAULT_COLOR).strip() or DEFAULT_COLOR
        note = str(note or '').strip()[:MAX_NOTE_LEN] or None
        return AnnotationRepository.update_annotation(db_type, annotation_id, user_id, color, note)

    @staticmethod
    def delete_annotation(db_type, annotation_id, user_id):
        return AnnotationRepository.delete_annotation(db_type, annotation_id, user_id)
