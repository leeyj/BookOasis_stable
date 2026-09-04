# -*- coding: utf-8 -*-
"""reading_review.py — 독후감 아카이브 (Reading Review Archive)

코어 개발자가 직접 만드는 "본격" 플러그인 샘플. 기존 샘플들이 계약 하나씩만
보여주는 최소 예제였다면, 이 플러그인은 실제로 쓸 수 있는 기능(도서 검색 →
별점/태그/스포일러 여부와 함께 독후감 작성 → 목록/통계 조회 → 도서 카드에서
바로 진입)을 하나로 묶어서 여러 계약을 함께 활용하는 법을 보여준다.

이 플러그인이 보여주는 것:

  1. category_tab 풀페이지 UI 하나로 검색/작성/목록/통계 4가지 화면을 구현.
  2. get_context_menu_items/run_context_menu_action을 "메뉴 클릭 액션"뿐 아니라
     풀페이지 UI 자신의 범용 RPC 채널로도 재사용하는 패턴. 코어는
     `/api/media/context-menu/book/plugins/action` 엔드포인트가 로그인 세션만
     확인하고 그대로 plugin.run_context_menu_action(db_type, action_id, context)
     를 호출해주므로, 실제로 컨텍스트 메뉴가 열려 있지 않아도 script.js가 이
     엔드포인트를 직접 fetch()해서 "책 검색", "리뷰 저장", "통계 조회" 같은
     임의의 액션을 호출할 수 있다. action_id를 여러 개 분기해서 사실상 작은
     REST API처럼 쓰는 셈이다.
  3. 도서 카드 컨텍스트 메뉴 → 카테고리 탭으로의 "포커스 핸드오프". 컨텍스트
     메뉴 액션 응답에 `open_category: 'plugin_<plugin_id>'`를 실어 보내면
     프런트(static/js/book_context_menu.js)가 새 탭을 띄우는 대신 바로 그
     카테고리 플러그인 풀페이지로 앱 내부 이동(selectCategory)해준다 — 도서
     카드에서 메뉴 클릭 한 번으로 곧장 이 플러그인 화면까지 들어오는 것이다.
     다만 이동 자체는 "화면 전환"일 뿐 어떤 책을 위해 왔는지는 넘겨주지
     않으므로, 그 책 정보는 플러그인이 자신의 저장소에 "이 사용자가 마지막으로
     선택한 책" 1행짜리 focus 레코드로 따로 기록해두고, 풀페이지 UI가 열릴 때
     그 값을 읽어와 작성 폼을 자동으로 채운다.
  4. 코어 DB는 읽기 전용으로만 조회(get_db_gateway로 books/user_progress를
     검색해 후보를 보여줄 뿐)하고, 실제 독후감 데이터는 코어 스키마를 전혀
     건드리지 않는 플러그인 전용 SQLite 파일에 저장 — highlight_notes_sample과
     같은 철학이지만 여기서는 SQLite를 써서 검색/정렬/집계 쿼리가 필요한
     본격적인 데이터를 다루는 법을 보여준다.
  5. dashboard_widget에서 최근 작성한 독후감을 "도서 카드" 형태 아이템으로
     반환해 클릭 시 바로 리더로 이동하게 만드는 법(대시보드 위젯 아이템 스펙
     중 book_id + file_format 조합을 쓰는 케이스).
  6. 본문은 Markdown으로 작성/저장하고(코어가 이미 전역 로드해두는 marked.js를
     재사용, 새 라이브러리 추가 없음), 내보내기는 YAML 프런트매터 + Markdown
     본문 하나로 통일해 "파일로 저장"과 향후 "사용자간 공유"가 같은 포맷을
     그대로 쓸 수 있게 설계했다 (export_review/export_all_reviews 참고).

주의: 동시쓰기 경합/파일 손상 대비, 다중 서버 인스턴스 간 데이터 공유 같은
프로덕션급 견고성은 이 샘플 범위를 벗어난다 — 단일 SQLite 파일 + 짧은 트랜잭션
정도로 충분하다는 전제다.
"""
import base64
import io
import os
import re
import sqlite3
import threading
import time
import zipfile

from flask import session

from plugins.metadata.base import BaseMetadataProvider


class ReadingReviewProvider(BaseMetadataProvider):
    """도서별 독후감(별점/태그/스포일러/본문)을 작성·관리하는 카테고리 레벨 플러그인."""

    id = "reading_review"
    name = "독후감 아카이브"
    is_searchable = False
    config_schema = [
        {
            "key": "DEFAULT_SORT",
            "label": "기본 정렬",
            "type": "select",
            "default": "recent",
            "options": [
                {"value": "recent", "label": "최근 작성순"},
                {"value": "rating", "label": "별점 높은순"},
                {"value": "title", "label": "책 제목순"},
            ],
        },
    ]
    dashboard_widget = {
        "title": "독후감 아카이브",
        "subtitle": "최근에 남긴 독후감",
        "provider": "BookOasis",
        "icon": "fa-solid fa-feather-pointed",
        "limit": 5,
    }
    category_tab = {
        "title": "독후감 아카이브",
        "icon": "fa-solid fa-feather-pointed",
        "order": 85,
        "sessions": "all",
    }
    update_manifest = {
        "enabled": True,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/leeyj/BookOasis/main/plugins/metadata/reading_review",
        "files": ["reading_review.py", "__init__.py", "VERSION", "index.html", "style.css", "script.js"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": True,
    }

    _db_lock = threading.Lock()

    # ────────────────────────────────────────────────────────────────
    # BaseMetadataProvider 필수 계약 — 이 플러그인은 검색형 메타데이터
    # 제공자가 아니므로 "지원하지 않음"만 명확히 반환한다.
    # ────────────────────────────────────────────────────────────────
    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "독후감 아카이브 플러그인은 메타데이터 적용을 지원하지 않습니다."

    # ────────────────────────────────────────────────────────────────
    # 플러그인 전용 SQLite 저장소
    # ────────────────────────────────────────────────────────────────
    def _get_storage_path(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(plugin_dir, "reading_reviews.sqlite3")

    def _get_conn(self):
        conn = sqlite3.connect(self._get_storage_path(), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self, conn):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_type TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                book_id INTEGER,
                book_title TEXT NOT NULL,
                series_name TEXT,
                author TEXT,
                cover_image TEXT,
                file_format TEXT,
                rating INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '',
                spoiler INTEGER NOT NULL DEFAULT 0,
                finished_date TEXT,
                body TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reviews_scope ON reviews(db_type, user_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS focus (
                user_id INTEGER NOT NULL,
                db_type TEXT NOT NULL,
                book_id INTEGER,
                book_title TEXT,
                series_name TEXT,
                author TEXT,
                cover_image TEXT,
                file_format TEXT,
                set_at REAL,
                PRIMARY KEY (user_id, db_type)
            )
            """
        )
        conn.commit()

    def _with_conn(self, fn):
        with self._db_lock:
            conn = self._get_conn()
            try:
                self._ensure_schema(conn)
                return fn(conn)
            finally:
                conn.close()

    @staticmethod
    def _resolve_cover_url(cover_image):
        """books.cover_image의 원본 저장값(파일명/상대경로)을 브라우저가 바로
        쓸 수 있는 /covers/... URL로 정규화한다. 이미 절대 URL이면 그대로 둔다."""
        if not cover_image:
            return None
        clean = str(cover_image).strip()
        if not clean:
            return None
        if clean.startswith("http://") or clean.startswith("https://") or clean.startswith("/"):
            return clean
        clean = clean.lstrip("/\\")
        if clean.lower().startswith("covers/"):
            clean = clean[len("covers/"):].lstrip("/\\")
        return f"/covers/{clean}" if clean else None

    @staticmethod
    def _row_to_review(row):
        return {
            "id": row["id"],
            "db_type": row["db_type"],
            "book_id": row["book_id"],
            "book_title": row["book_title"],
            "series_name": row["series_name"],
            "author": row["author"],
            "cover_image": row["cover_image"],
            "file_format": row["file_format"],
            "rating": row["rating"],
            "tags": [t for t in (row["tags"] or "").split(",") if t],
            "spoiler": bool(row["spoiler"]),
            "finished_date": row["finished_date"],
            "body": row["body"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ────────────────────────────────────────────────────────────────
    # 현재 로그인 사용자 식별
    # ────────────────────────────────────────────────────────────────
    def _current_user_id(self):
        try:
            return session.get("user_id")
        except RuntimeError:
            # 요청 컨텍스트 밖(예: 백그라운드 스레드)에서 호출된 경우
            return None

    # ────────────────────────────────────────────────────────────────
    # 도서 카드 컨텍스트 메뉴 — "독후감 쓰기" 진입점 + 포커스 핸드오프
    # ────────────────────────────────────────────────────────────────
    def get_context_menu_items(self, db_type, context):
        book_id = context.get("book_id")
        has_review = False
        if book_id:
            def _count(conn):
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM reviews WHERE db_type=? AND book_id=?",
                    (db_type, book_id),
                ).fetchone()
                return row["c"] if row else 0

            try:
                has_review = self._with_conn(_count) > 0
            except Exception:
                has_review = False

        return [
            {
                "id": "open_reading_review",
                "label": "독후감 다시 보기 (아카이브에서 열기)" if has_review else "독후감 쓰기 (아카이브에서 열기)",
                "icon": "fa-solid fa-feather-pointed",
            }
        ]

    def run_context_menu_action(self, db_type, action_id, context):
        handlers = {
            "open_reading_review": self._action_open_reading_review,
            "search_books": self._action_search_books,
            "list_reviews": self._action_list_reviews,
            "get_review": self._action_get_review,
            "save_review": self._action_save_review,
            "delete_review": self._action_delete_review,
            "get_stats": self._action_get_stats,
            "get_focus": self._action_get_focus,
            "clear_focus": self._action_clear_focus,
            "export_review": self._action_export_review,
            "export_all_reviews": self._action_export_all_reviews,
        }
        handler = handlers.get(action_id)
        if not handler:
            return {"success": False, "error": f"지원하지 않는 액션입니다: {action_id}"}

        user_id = self._current_user_id()
        if not user_id:
            return {"success": False, "error": "로그인 세션이 필요합니다."}

        try:
            return handler(db_type, context, user_id)
        except Exception as e:
            return {"success": False, "error": f"처리 중 오류가 발생했습니다: {e}"}

    # ── 액션: 도서 카드 컨텍스트 메뉴에서 클릭 시, 풀페이지 탭에 넘길 "포커스" 기록 ──
    def _action_open_reading_review(self, db_type, context, user_id):
        book_id = context.get("book_id")
        book_title = context.get("book_title") or ""

        cover_image = None
        author = None
        file_format = None
        series_name = None
        if book_id:
            gateway = self.get_db_gateway(db_type)
            row = gateway.fetch_one(
                "SELECT title, series_name, author, cover_image, file_format FROM books WHERE id=? AND COALESCE(is_deleted,0)=0",
                (book_id,),
            )
            if row:
                # 시리즈(만화 등 여러 권)라면 "1권", "12화" 같은 개별 권 제목이 아니라
                # 시리즈 이름으로 독후감을 걸어야 자연스럽다 — 어느 권의 카드에서 열어도
                # 항상 같은 시리즈 식별자로 수렴하게 한다. 단권이면 series_name이
                # 비어 있으니 그대로 title을 쓴다.
                series_name = row["series_name"]
                book_title = series_name or row["title"] or book_title
                author = row["author"]
                cover_image = self._resolve_cover_url(row["cover_image"])
                file_format = row["file_format"]

        def _write(conn):
            conn.execute(
                """
                INSERT INTO focus (user_id, db_type, book_id, book_title, series_name, author, cover_image, file_format, set_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, db_type) DO UPDATE SET
                    book_id=excluded.book_id, book_title=excluded.book_title,
                    series_name=excluded.series_name, author=excluded.author,
                    cover_image=excluded.cover_image, file_format=excluded.file_format,
                    set_at=excluded.set_at
                """,
                (user_id, db_type, book_id, book_title, series_name, author, cover_image, file_format, time.time()),
            )
            conn.commit()

        self._with_conn(_write)
        return {
            "success": True,
            "message": f"'{book_title}' 독후감 아카이브로 이동합니다.",
            "open_category": f"plugin_{self.id}",
        }

    def _action_get_focus(self, db_type, context, user_id):
        def _read(conn):
            row = conn.execute(
                "SELECT * FROM focus WHERE user_id=? AND db_type=?",
                (user_id, db_type),
            ).fetchone()
            return dict(row) if row else None

        focus = self._with_conn(_read)
        return {"success": True, "focus": focus}

    def _action_clear_focus(self, db_type, context, user_id):
        def _clear(conn):
            conn.execute("DELETE FROM focus WHERE user_id=? AND db_type=?", (user_id, db_type))
            conn.commit()

        self._with_conn(_clear)
        return {"success": True}

    # ── 액션: 코어 books 테이블에서 후보 검색 (읽기 전용) ──
    #
    # 만화처럼 여러 권으로 나뉜 시리즈를 그대로 검색하면 권수만큼 결과가 쏟아지고,
    # 사용자는 보통 맨 위(대개 1권)를 무심코 고르게 된다 — 그런데 독후감은 보통
    # "시리즈를 다 읽고" 쓰는 것이라 1권에 묶이는 게 어색하다. 그래서 코어가
    # 라이브러리 그리드에서 시리즈를 묶을 때 쓰는 것과 동일한 그룹핑 키
    # (series_name이 있으면 그것, 없으면 title 자신 — repositories/mariadb/series_repository.py
    # 참고)로 묶어서, 시리즈는 대표 권 하나로만 노출하고 이름도 "1권"이 아니라
    # 시리즈 이름으로 보여준다. 단권 도서는 지금까지와 동일하게 한 줄씩 나온다.
    def _action_search_books(self, db_type, context, user_id):
        query = str(context.get("query") or "").strip()
        if not query:
            return {"success": True, "items": []}

        gateway = self.get_db_gateway(db_type)
        like = f"%{query}%"
        groups = gateway.fetch_all(
            """
            SELECT
                COALESCE(NULLIF(series_name,''), title) AS series_key,
                COUNT(*) AS volume_count,
                MIN(id) AS rep_id
            FROM books
            WHERE COALESCE(is_deleted,0)=0
              AND (title LIKE ? OR series_name LIKE ? OR author LIKE ?)
            GROUP BY COALESCE(NULLIF(series_name,''), title)
            ORDER BY series_key ASC
            LIMIT 20
            """,
            (like, like, like),
        ) or []

        rep_ids = [g["rep_id"] for g in groups]
        if not rep_ids:
            return {"success": True, "items": []}

        placeholders = ",".join("?" for _ in rep_ids)
        rep_rows = gateway.fetch_all(
            f"""
            SELECT id, title, series_name, author, cover_image, file_format, total_pages
            FROM books WHERE id IN ({placeholders})
            """,
            tuple(rep_ids),
        ) or []
        rep_by_id = {r["id"]: r for r in rep_rows}

        items = []
        for g in groups:
            rep = rep_by_id.get(g["rep_id"])
            if not rep:
                continue
            volume_count = int(g["volume_count"] or 1)
            display_title = rep["series_name"] or rep["title"]
            items.append(
                {
                    "book_id": rep["id"],
                    "title": display_title,
                    "series_name": rep["series_name"],
                    "author": rep["author"],
                    "cover_image": self._resolve_cover_url(rep["cover_image"]),
                    "file_format": rep["file_format"],
                    "total_pages": rep["total_pages"],
                    "volume_count": volume_count,
                }
            )
        return {"success": True, "items": items}

    # ── 액션: 내가 쓴 독후감 목록 (검색/정렬/필터) ──
    def _action_list_reviews(self, db_type, context, user_id):
        sort = context.get("sort") or "recent"
        query = str(context.get("query") or "").strip()
        min_rating = int(context.get("min_rating") or 0)

        sql = "SELECT * FROM reviews WHERE db_type=? AND user_id=?"
        params = [db_type, user_id]
        if query:
            sql += " AND (book_title LIKE ? OR tags LIKE ? OR body LIKE ?)"
            like = f"%{query}%"
            params += [like, like, like]
        if min_rating > 0:
            sql += " AND rating >= ?"
            params.append(min_rating)

        if sort == "rating":
            sql += " ORDER BY rating DESC, updated_at DESC"
        elif sort == "title":
            sql += " ORDER BY book_title ASC"
        else:
            sql += " ORDER BY updated_at DESC"

        def _read(conn):
            return [self._row_to_review(r) for r in conn.execute(sql, params).fetchall()]

        reviews = self._with_conn(_read)
        return {"success": True, "items": reviews}

    def _action_get_review(self, db_type, context, user_id):
        review_id = context.get("review_id")
        if not review_id:
            return {"success": False, "error": "review_id가 필요합니다."}

        def _read(conn):
            row = conn.execute(
                "SELECT * FROM reviews WHERE id=? AND db_type=? AND user_id=?",
                (review_id, db_type, user_id),
            ).fetchone()
            return self._row_to_review(row) if row else None

        review = self._with_conn(_read)
        if not review:
            return {"success": False, "error": "존재하지 않는 독후감입니다."}
        return {"success": True, "review": review}

    # ── 액션: 독후감 작성/수정 ──
    def _action_save_review(self, db_type, context, user_id):
        book_title = str(context.get("book_title") or "").strip()
        if not book_title:
            return {"success": False, "error": "책 제목이 필요합니다."}

        try:
            rating = max(0, min(5, int(context.get("rating") or 0)))
        except (TypeError, ValueError):
            rating = 0

        tags_raw = context.get("tags")
        if isinstance(tags_raw, list):
            tags = ",".join(str(t).strip() for t in tags_raw if str(t).strip())
        else:
            tags = ",".join(t.strip() for t in str(tags_raw or "").split(",") if t.strip())

        body = str(context.get("body") or "").strip()
        spoiler = 1 if context.get("spoiler") else 0
        finished_date = context.get("finished_date") or None
        book_id = context.get("book_id")
        series_name = context.get("series_name")
        author = context.get("author")
        cover_image = context.get("cover_image")
        file_format = context.get("file_format")
        review_id = context.get("review_id")
        now = time.time()

        def _write(conn):
            if review_id:
                row = conn.execute(
                    "SELECT id FROM reviews WHERE id=? AND db_type=? AND user_id=?",
                    (review_id, db_type, user_id),
                ).fetchone()
                if not row:
                    return None
                conn.execute(
                    """
                    UPDATE reviews SET book_id=?, book_title=?, series_name=?, author=?,
                        cover_image=?, file_format=?, rating=?, tags=?, spoiler=?,
                        finished_date=?, body=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        book_id, book_title, series_name, author, cover_image, file_format,
                        rating, tags, spoiler, finished_date, body, now, review_id,
                    ),
                )
                conn.commit()
                return review_id

            cur = conn.execute(
                """
                INSERT INTO reviews (
                    db_type, user_id, book_id, book_title, series_name, author,
                    cover_image, file_format, rating, tags, spoiler, finished_date,
                    body, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    db_type, user_id, book_id, book_title, series_name, author,
                    cover_image, file_format, rating, tags, spoiler, finished_date,
                    body, now, now,
                ),
            )
            conn.commit()
            return cur.lastrowid

        new_id = self._with_conn(_write)
        if not new_id:
            return {"success": False, "error": "수정할 독후감을 찾지 못했습니다."}
        return {"success": True, "message": "독후감이 저장되었습니다.", "review_id": new_id}

    def _action_delete_review(self, db_type, context, user_id):
        review_id = context.get("review_id")
        if not review_id:
            return {"success": False, "error": "review_id가 필요합니다."}

        def _delete(conn):
            cur = conn.execute(
                "DELETE FROM reviews WHERE id=? AND db_type=? AND user_id=?",
                (review_id, db_type, user_id),
            )
            conn.commit()
            return cur.rowcount

        deleted = self._with_conn(_delete)
        if not deleted:
            return {"success": False, "error": "존재하지 않는 독후감입니다."}
        return {"success": True, "message": "독후감이 삭제되었습니다."}

    # ── 액션: 통계 (총계/평균 별점/태그 빈도/월별 작성 추이) ──
    def _action_get_stats(self, db_type, context, user_id):
        def _read(conn):
            rows = conn.execute(
                "SELECT rating, tags, created_at FROM reviews WHERE db_type=? AND user_id=?",
                (db_type, user_id),
            ).fetchall()
            return [dict(r) for r in rows]

        rows = self._with_conn(_read)
        total = len(rows)
        avg_rating = round(sum(r["rating"] for r in rows) / total, 2) if total else 0.0

        tag_counts = {}
        monthly_counts = {}
        for r in rows:
            for t in (r["tags"] or "").split(","):
                t = t.strip()
                if t:
                    tag_counts[t] = tag_counts.get(t, 0) + 1
            month_key = time.strftime("%Y-%m", time.localtime(r["created_at"]))
            monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

        top_tags = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        recent_months = sorted(monthly_counts.items())[-6:]

        return {
            "success": True,
            "stats": {
                "total_reviews": total,
                "avg_rating": avg_rating,
                "top_tags": [{"tag": k, "count": v} for k, v in top_tags],
                "monthly": [{"month": k, "count": v} for k, v in recent_months],
            },
        }

    # ────────────────────────────────────────────────────────────────
    # 내보내기 (Markdown + YAML 프런트매터)
    #
    # 지금은 "내 컴퓨터로 파일 저장" 용도지만, 이 포맷 하나로 향후 "사용자간 독후감
    # 공유" 기능이 붙을 때도 그대로 재사용할 수 있도록 일부러 자기완결적으로 만들었다
    # (프런트매터에 책 식별 정보 + 별점/태그/스포일러/완독일이 전부 들어있어서, 이
    # 파일 하나만 다른 서버/다른 사용자에게 넘겨도 복원에 필요한 정보가 충분하다).
    # 공유 기능이 실제로 붙을 때는 여기서 만드는 텍스트를 그대로 payload로 재사용하고,
    # 그때 가서 진짜 신경 써야 할 것(HTML 렌더링 시 XSS 새니타이징, 프런트매터 파서의
    # 악의적 입력 방어 등)을 다루면 된다 — 지금은 "내 파일을 내가 내려받는" 것뿐이라
    # 그 위험이 없다.
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _slugify_filename(text, fallback="review"):
        text = str(text or "").strip()
        # 파일시스템에서 문제가 되는 문자만 제거하고 나머지(한글 포함)는 그대로 둔다.
        text = re.sub(r'[\\/:*?"<>|\r\n\t]', "", text).strip()
        return text or fallback

    @staticmethod
    def _yaml_scalar(value):
        """YAML 프런트매터에 안전하게 넣기 위해 문자열은 항상 따옴표로 감싼다
        (콜론/해시 등 YAML 특수문자가 책 제목에 섞여 있어도 깨지지 않도록)."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _review_to_markdown(self, review):
        tags_yaml = "[" + ", ".join(self._yaml_scalar(t) for t in review["tags"]) + "]"
        front_matter_lines = [
            "---",
            f"title: {self._yaml_scalar(review['book_title'])}",
            f"series_name: {self._yaml_scalar(review['series_name'])}",
            f"author: {self._yaml_scalar(review['author'])}",
            f"rating: {review['rating']}",
            f"tags: {tags_yaml}",
            f"spoiler: {self._yaml_scalar(review['spoiler'])}",
            f"finished_date: {self._yaml_scalar(review['finished_date'])}",
            f"created_at: {self._yaml_scalar(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(review['created_at'])))}",
            f"updated_at: {self._yaml_scalar(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(review['updated_at'])))}",
            "source: BookOasis / 독후감 아카이브 플러그인",
            "---",
            "",
        ]
        return "\n".join(front_matter_lines) + (review["body"] or "")

    def _action_export_review(self, db_type, context, user_id):
        review_id = context.get("review_id")
        if not review_id:
            return {"success": False, "error": "review_id가 필요합니다."}

        def _read(conn):
            row = conn.execute(
                "SELECT * FROM reviews WHERE id=? AND db_type=? AND user_id=?",
                (review_id, db_type, user_id),
            ).fetchone()
            return self._row_to_review(row) if row else None

        review = self._with_conn(_read)
        if not review:
            return {"success": False, "error": "존재하지 않는 독후감입니다."}

        filename = f"{self._slugify_filename(review['book_title'])}.md"
        return {
            "success": True,
            "filename": filename,
            "content": self._review_to_markdown(review),
        }

    def _action_export_all_reviews(self, db_type, context, user_id):
        # 목록 탭과 동일한 검색/정렬/필터 조건을 그대로 받아, "지금 화면에 보이는
        # 독후감들"을 내보낸다는 사용자 기대와 일치시킨다.
        list_result = self._action_list_reviews(db_type, context, user_id)
        reviews = list_result.get("items", [])
        if not reviews:
            return {"success": False, "error": "내보낼 독후감이 없습니다."}

        buffer = io.BytesIO()
        used_names = set()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for review in reviews:
                base_name = self._slugify_filename(review["book_title"])
                name = f"{base_name}.md"
                dedup = 2
                while name in used_names:
                    name = f"{base_name} ({dedup}).md"
                    dedup += 1
                used_names.add(name)
                zf.writestr(name, self._review_to_markdown(review))

        zip_bytes = buffer.getvalue()
        return {
            "success": True,
            "filename": f"reading_reviews_{db_type}_{time.strftime('%Y%m%d')}.zip",
            "content_base64": base64.b64encode(zip_bytes).decode("ascii"),
            "count": len(reviews),
        }

    # ────────────────────────────────────────────────────────────────
    # 대시보드 위젯 — 최근 독후감을 도서 카드 형태로 노출 (클릭 시 리더로 이동)
    # ────────────────────────────────────────────────────────────────
    def get_dashboard_data(self, db_type, limit=5):
        user_id = self._current_user_id()
        if not user_id:
            return {"success": True, "items": []}

        def _read(conn):
            self._ensure_schema(conn)
            rows = conn.execute(
                "SELECT * FROM reviews WHERE db_type=? AND user_id=? ORDER BY updated_at DESC LIMIT ?",
                (db_type, user_id, max(1, int(limit or 5))),
            ).fetchall()
            return [self._row_to_review(r) for r in rows]

        reviews = self._with_conn(_read)
        items = []
        for r in reviews:
            stars = "★" * r["rating"] + "☆" * (5 - r["rating"])
            items.append(
                {
                    "title": r["book_title"],
                    "author": r["author"] or "",
                    "publisher": stars,
                    "pubDate": time.strftime("%Y-%m-%d", time.localtime(r["updated_at"])),
                    "cover": r["cover_image"] or None,
                    "book_id": r["book_id"],
                    "file_format": r["file_format"],
                    "series_name": r["series_name"],
                }
            )
        return {"success": True, "items": items}
