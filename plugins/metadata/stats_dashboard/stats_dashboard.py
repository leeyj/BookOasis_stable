# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from plugins.metadata.base import BaseMetadataProvider


class StatsDashboardMetadataProvider(BaseMetadataProvider):
    """Dashboard statistics widget example plugin."""

    id = "stats_dashboard"
    name = "통계 대시보드 위젯"
    is_searchable = False
    config_schema = []
    dashboard_widget = {
        "title": "독서 통계",
        "subtitle": "주간/월간 독서 및 라이브러리 요약",
        "provider": "BookOasis",
        "icon": "fa-solid fa-chart-column",
        "limit": 3,
        "all_desk_tab": True,
    }
    update_manifest = {
        "enabled": True,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/leeyj/BookOasis_stable/main/plugins/metadata/stats_dashboard",
        "files": ["stats_dashboard.py", "__init__.py", "VERSION"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": True,
    }

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "통계 위젯 플러그인은 메타데이터 적용을 지원하지 않습니다."

    def _week_start(self):
        now = datetime.now()
        monday = now - timedelta(days=now.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)

    def _month_start(self):
        now = datetime.now()
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _fetch_stats(self, db_type):
        gateway = self.get_db_gateway(db_type)
        week_start = self._week_start().strftime("%Y-%m-%d %H:%M:%S")
        month_start = self._month_start().strftime("%Y-%m-%d %H:%M:%S")

        totals = gateway.fetch_one(
            """
            SELECT
                COUNT(*) AS total_books,
                COUNT(DISTINCT CASE
                    WHEN TRIM(COALESCE(series_name, '')) != '' THEN TRIM(series_name)
                    ELSE '__single__:' || CAST(id AS TEXT)
                END) AS total_series
            FROM books
            WHERE COALESCE(is_deleted, 0) = 0
            """
        )

        weekly_completed = gateway.fetch_one(
            """
            SELECT COUNT(DISTINCT p.book_id) AS weekly_completed
            FROM user_progress p
            JOIN books b ON b.id = p.book_id
            WHERE COALESCE(b.is_deleted, 0) = 0
              AND p.last_read_at >= ?
              AND (
                COALESCE(p.is_completed, 0) = 1
                OR (COALESCE(b.total_pages, 0) > 0 AND COALESCE(p.pages_read, 0) >= b.total_pages)
              )
            """,
            (week_start,),
        )

        monthly_completed = gateway.fetch_one(
            """
            SELECT COUNT(DISTINCT p.book_id) AS monthly_completed
            FROM user_progress p
            JOIN books b ON b.id = p.book_id
            WHERE COALESCE(b.is_deleted, 0) = 0
              AND p.last_read_at >= ?
              AND (
                COALESCE(p.is_completed, 0) = 1
                OR (COALESCE(b.total_pages, 0) > 0 AND COALESCE(p.pages_read, 0) >= b.total_pages)
              )
            """,
            (month_start,),
        )

        weekly_new = gateway.fetch_one(
            """
            SELECT COUNT(*) AS weekly_new
            FROM books
            WHERE COALESCE(is_deleted, 0) = 0
              AND created_at >= ?
            """,
            (week_start,),
        )

        monthly_new = gateway.fetch_one(
            """
            SELECT COUNT(*) AS monthly_new
            FROM books
            WHERE COALESCE(is_deleted, 0) = 0
              AND created_at >= ?
            """,
            (month_start,),
        )

        return {
            "total_books": int((totals["total_books"] if totals else 0) or 0),
            "total_series": int((totals["total_series"] if totals else 0) or 0),
            "weekly_completed": int((weekly_completed["weekly_completed"] if weekly_completed else 0) or 0),
            "monthly_completed": int((monthly_completed["monthly_completed"] if monthly_completed else 0) or 0),
            "weekly_new": int((weekly_new["weekly_new"] if weekly_new else 0) or 0),
            "monthly_new": int((monthly_new["monthly_new"] if monthly_new else 0) or 0),
        }

    def get_dashboard_data(self, db_type, limit=3):
        stats = self._fetch_stats(db_type)
        items = [
            {
                "item_type": "metric",
                "metric": "총계: 시리즈 수/도서수",
                "value": f"{stats['total_series']} / {stats['total_books']}권",
                "description": "현재 라이브러리 기준",
            },
            {
                "item_type": "metric",
                "metric": "읽은 도서 수(100%완독기준)",
                "value": f"이번주 {stats['weekly_completed']}권 / 이번달 {stats['monthly_completed']}권",
                "description": "주간: 월요일 00:00 이후, 월간: 매월 1일 00:00 이후",
            },
            {
                "item_type": "metric",
                "metric": "신규 추가 수",
                "value": f"이번주 {stats['weekly_new']}권 / 이번달 {stats['monthly_new']}권",
                "description": "주간: 월요일 00:00 이후, 월간: 매월 1일 00:00 이후 등록",
            },
        ]

        return {"success": True, "items": items[: max(1, int(limit or 3))]}

    def get_context_menu_items(self, db_type, context):
        return [
            {
                "id": "show_reading_stats_summary",
                "label": "독서 통계 요약 보기",
                "icon": "fa-solid fa-chart-column",
            }
        ]

    def run_context_menu_action(self, db_type, action_id, context):
        if action_id != "show_reading_stats_summary":
            return {"success": False, "error": f"지원하지 않는 액션입니다: {action_id}"}

        stats = self._fetch_stats(db_type)
        message = (
            f"독서 통계: 총 {stats['total_series']}시리즈/{stats['total_books']}권, "
            f"완독 이번주 {stats['weekly_completed']}권/이번달 {stats['monthly_completed']}권, "
            f"신규 이번주 {stats['weekly_new']}권/이번달 {stats['monthly_new']}권"
        )
        return {"success": True, "message": message}
