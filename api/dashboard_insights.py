# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request, session
import datetime
from collections import Counter
from services.reading_history_service import ReadingHistoryService
from repositories.settings_repository import SettingsRepository
from repositories.reading_progress_repository import ReadingProgressRepository

dashboard_insights_bp = Blueprint('dashboard_insights_api', __name__)

@dashboard_insights_bp.route('/api/dashboard/insights', methods=['GET'])
def get_dashboard_insights():
    try:
        user_id = session.get('user_id')
        if not user_id:
            user_id = session.get('user_id', 1)

        db_type = request.args.get('library_type', 'general')
        if db_type not in ('general', 'adult', 'audiobook', 'video'):
            db_type = 'general'

        if db_type == 'adult':
            from api.auth import check_adult_permission
            if not check_adult_permission('adult'):
                return jsonify({'success': False, 'error': '성인 카테고리 접근 권한이 없습니다.'}), 403

        # 1. Currently Reading & 히스토리 도서 목록 (검증된 ReadingHistoryService 활용)
        currently_reading = []
        history_books = []
        try:
            history_books = ReadingHistoryService.get_history(db_type, user_id=user_id) or []
            for b in history_books:
                is_comp = b.get('is_completed', 0) == 1
                pages_read = b.get('pages_read', 0)
                total_pages = b.get('total_pages', 0)
                
                if not is_comp and pages_read > 0:
                    pct = int(min(99, round((pages_read / total_pages) * 100))) if total_pages > 0 else 10
                    item_dict = dict(b)
                    item_dict['progress_pct'] = max(1, min(98, pct))
                    item_dict['format'] = item_dict.get('file_format', '')
                    item_dict['cover_url'] = b.get('cover_image') or f'/api/cover/{b["id"]}?type={db_type}'
                    currently_reading.append(item_dict)
                    if len(currently_reading) >= 2:
                        break
        except Exception as e:
            print(f"[Insights] Reading history error: {e}")

        # DB settings 테이블에서 저장된 연간 목표 권수 읽기
        target_annual_books = 30
        try:
            val = SettingsRepository.get_value(db_type, 'ANNUAL_READING_GOAL')
            if val and str(val).isdigit():
                target_annual_books = max(1, int(val))
        except Exception as e:
            print(f"[Insights] Read ANNUAL_READING_GOAL error: {e}")

        # 2. Reading Streak & Last 7 Days
        streak_days = 0
        last_7_days = [False] * 7
        today = datetime.date.today()
        
        try:
            read_dates_set = set(ReadingProgressRepository.get_distinct_read_dates(db_type, user_id))

            for i in range(7):
                day_target = today - datetime.timedelta(days=(6 - i))
                if day_target.strftime('%Y-%m-%d') in read_dates_set:
                    last_7_days[i] = True

            check_date = today
            if check_date.strftime('%Y-%m-%d') not in read_dates_set:
                check_date = today - datetime.timedelta(days=1)

            while check_date.strftime('%Y-%m-%d') in read_dates_set:
                streak_days += 1
                check_date -= datetime.timedelta(days=1)

            if streak_days == 0 and len(read_dates_set) > 0:
                streak_days = 1

        except Exception as e:
            print(f"[Insights] Streak query error: {e}")

        # 3. Annual Goal (2026 연간 완독 목표)
        completed_this_year = 0
        current_year = today.year
        try:
            completed_this_year = ReadingProgressRepository.get_completed_count_by_year(db_type, user_id, str(current_year))
        except Exception as e:
            print(f"[Insights] Annual goal error: {e}")

        annual_pct = min(100, int((completed_this_year / target_annual_books) * 100))

        # 4. Monthly Challenge
        completed_this_month = 0
        current_month_str = today.strftime('%Y-%m')
        try:
            completed_this_month = ReadingProgressRepository.get_completed_count_by_month(db_type, user_id, current_month_str)
        except Exception as e:
            print(f"[Insights] Monthly challenge error: {e}")

        target_monthly_books = 5
        monthly_pct = min(100, int((completed_this_month / target_monthly_books) * 100))

        # 5. Genre Breakdown 2026 (읽은 도서 장르/포맷 집계)
        genre_breakdown = []
        try:
            counts = Counter()
            for b in history_books:
                genre = b.get('genre') or b.get('category') or ''
                fmt = b.get('file_format') or ''
                
                if genre and str(genre).strip():
                    g_name = str(genre).strip()
                elif fmt and str(fmt).strip():
                    fmt_str = str(fmt).strip().upper()
                    if fmt_str in ('CBZ', 'CBR', 'ZIP', 'RAR'):
                        g_name = '만화책 (' + fmt_str + ')'
                    elif fmt_str == 'EPUB':
                        g_name = '전자책 (EPUB)'
                    elif fmt_str == 'TXT':
                        g_name = '텍스트 (TXT)'
                    elif fmt_str == 'PDF':
                        g_name = '문서 (PDF)'
                    elif fmt_str in ('MP3', 'M4B'):
                        g_name = '오디오북 (' + fmt_str + ')'
                    elif fmt_str == 'VIDEO':
                        g_name = '영상 강좌'
                    else:
                        g_name = fmt_str + ' 도서'
                else:
                    g_name = '기타/단행본'
                
                counts[g_name] += 1

            total_genre_cnt = sum(counts.values())
            colors = ['#a855f7', '#38bdf8', '#34d399', '#f97316', '#ec4899']

            for idx, (g_name, g_cnt) in enumerate(counts.most_common(4)):
                g_pct = int(round((g_cnt / total_genre_cnt) * 100)) if total_genre_cnt > 0 else 0
                genre_breakdown.append({
                    'name': g_name,
                    'count': g_cnt,
                    'pct': g_pct,
                    'color': colors[idx % len(colors)]
                })
        except Exception as e:
            print(f"[Insights] Genre breakdown error: {e}")

        return jsonify({
            'success': True,
            'streak': {
                'days': streak_days,
                'last_7_days': last_7_days
            },
            'currently_reading': currently_reading,
            'annual_goal': {
                'year': current_year,
                'target': target_annual_books,
                'completed': completed_this_year,
                'pct': annual_pct
            },
            'monthly_challenge': {
                'month_name': today.strftime('%B'),
                'target': target_monthly_books,
                'completed': completed_this_month,
                'pct': monthly_pct
            },
            'genre_breakdown': genre_breakdown
        })
    except Exception as e:
        print(f"[Insights API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_insights_bp.route('/api/dashboard/goal', methods=['POST'])
def save_reading_goal():
    """연간 독서 목표 권수 저장 API"""
    try:
        data = request.get_json() or {}
        target_books = data.get('target_books')
        if not target_books or not str(target_books).isdigit():
            return jsonify({'success': False, 'error': '유효한 목표 권수를 입력해주세요.'}), 400

        target_val = max(1, int(target_books))
        db_type = data.get('library_type', 'general')
        if db_type not in ('general', 'adult', 'audiobook', 'video'):
            db_type = 'general'

        for dt in ('general', db_type):
            try:
                SettingsRepository.set_value(dt, 'ANNUAL_READING_GOAL', str(target_val))
            except Exception as e:
                print(f"[Goal API Save Error] db: {dt}, err: {e}")

        return jsonify({'success': True, 'target_books': target_val})
    except Exception as e:
        print(f"[Goal API Error] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
