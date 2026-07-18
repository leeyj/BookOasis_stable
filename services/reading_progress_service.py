# -*- coding: utf-8 -*-
from datetime import datetime

import database
from services.webhook_dispatcher import (
    build_book_event_payload,
    dispatch_standard_book_event,
    _to_unix_timestamp,
)


class ReadingProgressService:
    @staticmethod
    def record_progress(db_type: str, book_id, page_idx: int, total_pages: int, user_id=1, epub_session=None):
        """독서 진행률 및 활동 로그 기록 (EPUB 및 TXT도 실제 챕터 단위를 그대로 사용)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT file_format, total_pages, title, author, publisher, series_name, created_at
            FROM books WHERE id = ?
            """,
            (book_id,),
        )
        book_row = cursor.fetchone()

        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = 0

        try:
            total_pages = int(total_pages)
        except Exception:
            total_pages = 0

        file_format = (book_row['file_format'] or '').lower() if book_row else ''
        is_epub = file_format == 'epub'

        # EPUB은 저장 단위를 0~100 퍼센트로 정규화하여 크로스 디바이스 오차를 줄인다.
        if is_epub:
            raw_total = max(1, total_pages)
            raw_idx = max(0, page_idx)
            normalized_percent = int(round(((raw_idx + 1) / raw_total) * 100))
            normalized_percent = max(0, min(100, normalized_percent))
            total_pages = 100
            page_idx = max(0, normalized_percent - 1)

        # 실제 프론트엔드에서 전달된 총 페이지(챕터) 수를 기반으로 DB 업데이트
        if total_pages > 0 and book_row and book_row['total_pages'] != total_pages:
            cursor.execute("UPDATE books SET total_pages = ? WHERE id = ?", (total_pages, book_id))

        cursor.execute(
            "SELECT pages_read, is_completed FROM user_progress WHERE book_id = ? AND user_id = ?",
            (book_id, user_id),
        )
        row = cursor.fetchone()
        old_completed = 1 if (row and row['is_completed'] == 1) else 0

        pages_read = page_idx + 1
        is_completed = 0
        if total_pages > 0:
            if (pages_read / total_pages) >= 0.95 or pages_read >= total_pages:
                is_completed = 1

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        epub_session = epub_session or {}
        last_epub_cfi = epub_session.get('cfi')
        last_epub_href = epub_session.get('href')
        last_epub_spine_index = epub_session.get('index')
        last_epub_percent = epub_session.get('percent')
        last_epub_fingerprint = epub_session.get('fingerprint')

        if is_epub:
            if last_epub_percent is None:
                last_epub_percent = max(0, min(100, int(page_idx + 1)))
            else:
                try:
                    last_epub_percent = int(round(float(last_epub_percent)))
                except Exception:
                    last_epub_percent = max(0, min(100, int(page_idx + 1)))
                last_epub_percent = max(0, min(100, last_epub_percent))

        has_epub_pointer_update = (
            last_epub_cfi is not None
            or last_epub_href is not None
            or last_epub_spine_index is not None
            or last_epub_percent is not None
            or last_epub_fingerprint is not None
        )
        last_epub_updated_at = now_str if has_epub_pointer_update else None

        if not row:
            # 경쟁 상태 대비: INSERT OR IGNORE 로 레코드 선삽입
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_progress (
                    book_id, user_id, pages_read, is_completed, last_read_at,
                    last_epub_cfi, last_epub_href, last_epub_spine_index,
                    last_epub_percent, last_epub_fingerprint, last_epub_updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    book_id,
                    user_id,
                    0,
                    0,
                    now_str,
                    None,
                    None,
                    None,
                    0,
                    None,
                    None,
                ),
            )
            delta = pages_read
        else:
            old_pages = row['pages_read']
            delta = max(0, pages_read - old_pages)

        # 레코드가 확실히 존재하므로 일괄 UPDATE 수행하여 최종 상태 저장
        if has_epub_pointer_update:
            cursor.execute(
                """
                UPDATE user_progress
                SET pages_read=?, is_completed=?, last_read_at=?,
                    last_epub_cfi=?, last_epub_href=?, last_epub_spine_index=?,
                    last_epub_percent=?, last_epub_fingerprint=?, last_epub_updated_at=?
                WHERE book_id=? AND user_id=?
                """,
                (
                    pages_read,
                    is_completed,
                    now_str,
                    last_epub_cfi,
                    last_epub_href,
                    last_epub_spine_index,
                    last_epub_percent,
                    last_epub_fingerprint,
                    last_epub_updated_at,
                    book_id,
                    user_id,
                ),
            )
        else:
            cursor.execute(
                "UPDATE user_progress SET pages_read=?, is_completed=?, last_read_at=? WHERE book_id=? AND user_id=?",
                (pages_read, is_completed, now_str, book_id, user_id),
            )

        if delta > 0:
            today_str = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT id FROM user_reading_log WHERE book_id=? AND user_id=? AND read_date=?",
                (book_id, user_id, today_str),
            )
            log_row = cursor.fetchone()
            if log_row:
                cursor.execute(
                    "UPDATE user_reading_log SET pages_read_delta=pages_read_delta+? WHERE id=?",
                    (delta, log_row['id']),
                )
            else:
                cursor.execute(
                    "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (?,?,?,60,?)",
                    (book_id, user_id, delta, today_str),
                )

        conn.commit()

        # 표준 이벤트 웹훅(book.read / book.finish) 발행
        try:
            account_name = f"user-{user_id}"
            try:
                cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
                user_row = cursor.fetchone()
                if user_row and user_row['username']:
                    account_name = str(user_row['username'])
            except Exception:
                pass

            effective_total_pages = total_pages if total_pages > 0 else (book_row['total_pages'] if book_row else 0)
            if effective_total_pages and effective_total_pages > 0:
                progress_percent = max(0, min(100, int(round((pages_read / effective_total_pages) * 100))))
            else:
                progress_percent = 0

            fmt = (book_row['file_format'] or '').lower() if book_row else ''
            location = None
            if fmt == 'epub':
                if last_epub_href:
                    location = last_epub_href
                elif last_epub_cfi:
                    location = last_epub_cfi
                elif last_epub_spine_index is not None:
                    location = f"spine:{last_epub_spine_index}"
            elif fmt == 'txt':
                location = f"chunk:{max(1, page_idx + 1)}"
            elif pages_read > 0:
                location = f"page:{pages_read}"

            metadata = {
                'type': 'book',
                'format': fmt,
                'title': (book_row['title'] if book_row else '') or '',
                'author': (book_row['author'] if book_row else '') or '',
                'publisher': (book_row['publisher'] if book_row else '') or '',
                'series': (book_row['series_name'] if book_row else '') or None,
                'seriesIndex': None,
                'progress': progress_percent,
                # Fixed-page formats only are truly stable; keep optional for clients.
                'totalPages': int(effective_total_pages) if effective_total_pages and effective_total_pages > 0 else None,
                'currentLocation': location,
                'addedAt': _to_unix_timestamp(book_row['created_at'] if book_row else None),
            }

            account = {
                'id': int(user_id),
                'title': account_name,
            }

            should_emit_read = delta > 0
            should_emit_finish = old_completed == 0 and is_completed == 1

            if should_emit_read:
                payload = build_book_event_payload('book.read', account=account, metadata=metadata, user=True)
                dispatch_standard_book_event(payload)

            if should_emit_finish:
                payload = build_book_event_payload('book.finish', account=account, metadata=metadata, user=True)
                dispatch_standard_book_event(payload)
        except Exception as webhook_err:
            print(f"[Progress Webhook] dispatch skipped due to error: {webhook_err}")
        finally:
            conn.close()

    @staticmethod
    def get_progress_state(db_type: str, book_id, user_id=1):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                b.file_format,
                b.total_pages,
                p.pages_read,
                p.last_read_at,
                p.last_epub_cfi,
                p.last_epub_href,
                p.last_epub_spine_index,
                p.last_epub_percent,
                p.last_epub_fingerprint,
                p.last_epub_updated_at
            FROM books b
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
            WHERE b.id = ?
            """,
            (user_id, book_id),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        file_format = (row['file_format'] or '').lower()
        total_pages = row['total_pages'] if row['total_pages'] is not None else 0
        pages_read = row['pages_read'] if row['pages_read'] is not None else 0
        last_epub_percent = row['last_epub_percent'] if row['last_epub_percent'] is not None else 0

        # 로드 시점에는 DB를 변경하지 않고, 응답 값만 비파괴 정규화
        if file_format == 'epub':
            normalized_total = 100
            normalized_pages = pages_read

            if last_epub_percent:
                normalized_pages = last_epub_percent

            try:
                normalized_pages = int(normalized_pages)
            except Exception:
                normalized_pages = 0

            normalized_pages = max(0, min(100, normalized_pages))

            total_pages = normalized_total
            pages_read = normalized_pages

        conn.close()

        return {
            'total_pages': total_pages,
            'pages_read': pages_read,
            'last_read_at': row['last_read_at'],
            'epub_session': {
                'cfi': row['last_epub_cfi'],
                'href': row['last_epub_href'],
                'index': row['last_epub_spine_index'],
                'percent': last_epub_percent,
                'fingerprint': row['last_epub_fingerprint'],
                'updatedAt': row['last_epub_updated_at'],
            },
        }
