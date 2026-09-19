# -*- coding: utf-8 -*-
"""
diagnose_home_latency.py – 홈 화면 진입 시 나가는 3개 요청(최근 읽은 도서 / 신규 추가 / 전체 합계)이
현재 DB 엔진(SQLite 또는 MariaDB)에서 실제로 얼마나 걸리는지 재는 읽기 전용 진단 도구.

서버가 쓰는 환경(.env)을 그대로 읽어서 같은 엔진·같은 저장소 메서드를 호출하며, SELECT만 실행한다
(DB 쓰기 없음, Redis 캐시에도 쓰지 않고 읽기만 한다). 웹 서비스가 돌고 있는 서버에서 실행한다:

    python tools/diagnose_home_latency.py                 # 진행 기록이 많은 사용자 상위 3명
    python tools/diagnose_home_latency.py --user-id 1     # 특정 사용자만
    python tools/diagnose_home_latency.py --db-type video --repeat 5
"""
import argparse
import os
import statistics
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.encoding_helper import force_utf8_stdio
force_utf8_stdio()

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
except Exception as env_error:
    print(f"[경고] .env 로드 실패: {env_error}", file=sys.stderr)

import database
from repositories.reading_progress_repository import ReadingProgressRepository
from repositories.series_repository import SeriesRepository
from utils.redis_helper import get_redis_client, make_key


def timed(fn, repeat):
    """fn을 repeat번 실행해 (첫 실행 ms, 이후 실행 중앙값 ms, 결과)를 반환한다."""
    samples = []
    result = None
    for _ in range(repeat):
        started = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - started) * 1000)
    rest = samples[1:] or samples
    return samples[0], statistics.median(rest), result


def top_users(db_type, limit):
    table, column, cond = {
        'audiobook': ('audiobook_progress', 'user_id', 'COALESCE(current_time, 0) > 0'),
        'video': ('video_progress', 'user_id', 'COALESCE(current_time, 0) > 0'),
    }.get(db_type, ('user_progress', 'user_id', 'COALESCE(pages_read, 0) > 0'))
    with database.connection(db_type) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {column} AS user_id, COUNT(*) AS n FROM {table} WHERE {cond} "
            f"GROUP BY {column} ORDER BY n DESC LIMIT {int(limit)}"
        )
        return [(row['user_id'], row['n']) for row in cursor.fetchall()]


def scalar(db_type, sql):
    with database.connection(db_type) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        row = cursor.fetchone()
        return list(dict(row).values())[0] if row else None


def redis_report(db_type, user_id, limit, hide):
    client = get_redis_client()
    if client is None:
        return 'Redis 미사용 (요청마다 DB 조회)'
    key = make_key(f"cache:history:v8:{db_type}:{user_id}:{limit}:{int(hide)}")
    try:
        ttl = client.ttl(key)
    except Exception as error:
        return f'Redis 조회 실패: {error}'
    if ttl is None or ttl < 0:
        return 'Redis 연결됨, 이 사용자의 히스토리 캐시는 현재 없음(다음 홈 진입은 DB 조회)'
    return f'Redis 캐시 있음 (남은 수명 {ttl}초, 그동안 홈 진입은 캐시 응답)'


def main():
    parser = argparse.ArgumentParser(description='홈 진입 요청(히스토리/신규/합계) 응답 시간 진단 (읽기 전용)')
    parser.add_argument('--db-type', default='general', choices=['general', 'adult', 'audiobook', 'video'])
    parser.add_argument('--user-id', type=int, default=None, help='생략하면 진행 기록이 많은 사용자 상위 3명')
    parser.add_argument('--repeat', type=int, default=3, help='측정 반복 횟수 (첫 실행과 이후 중앙값을 따로 보고)')
    args = parser.parse_args()
    db_type, repeat = args.db_type, max(2, args.repeat)

    engine = 'MariaDB' if database.is_mariadb_mode() else 'SQLite'
    print(f"엔진: {engine} | db_type: {db_type} | 반복: {repeat}회")

    books_table = {'audiobook': 'audiobooks', 'video': 'videos'}.get(db_type, 'books')
    print(f"{books_table} 행 수: {scalar(db_type, f'SELECT COUNT(*) FROM {books_table}'):,}")

    users = [(args.user_id, None)] if args.user_id is not None else top_users(db_type, 3)
    if not users:
        print('진행 기록이 있는 사용자가 없어 히스토리 측정을 건너뜁니다.')
        users = [(1, 0)]

    limit_setting = ReadingProgressRepository.get_settings_value(db_type, 'RECENT_BOOKS_LIMIT')
    limit = max(1, min(int(limit_setting), 100)) if limit_setting and str(limit_setting).isdigit() else 30
    hide_default = ReadingProgressRepository.get_settings_value(db_type, 'HIDE_COMPLETED_IN_HISTORY') == '1'
    print(f"히스토리 표시 개수 설정: {limit}, 완독 숨김 설정: {'켬' if hide_default else '끔'}")
    print('-' * 78)

    worst_history = 0.0
    for user_id, progress_rows in users:
        label = f"사용자 {user_id}" + (f" (진행 기록 {progress_rows:,}건)" if progress_rows is not None else '')
        print(label)
        for hide in (False, True):
            first, median, rows = timed(
                lambda: ReadingProgressRepository.fetch_reading_history(db_type, user_id, limit, hide), repeat
            )
            worst_history = max(worst_history, first)
            print(f"  히스토리 DB 조회 [완독 숨김 {'켬' if hide else '끔'}]: 첫 실행 {first:8.1f} ms | 이후 중앙값 {median:8.1f} ms | {len(rows)}행")
        print(f"  {redis_report(db_type, user_id, limit, hide_default)}")

    sample_user = users[0][0]
    first, median, rows = timed(
        lambda: ReadingProgressRepository.fetch_recently_added_all(db_type, sample_user), repeat
    )
    print(f"신규 추가 DB 조회: 첫 실행 {first:8.1f} ms | 이후 중앙값 {median:8.1f} ms | {len(rows)}행")
    worst_new = first

    first, median, _ = timed(
        lambda: SeriesRepository.fetch_grouping_totals(db_type, 'all', user_id=sample_user, role='admin'), repeat
    )
    print(f"전체 합계 DB 조회: 첫 실행 {first:8.1f} ms | 이후 중앙값 {median:8.1f} ms")
    worst_totals = first

    print('-' * 78)
    # 브라우저는 세 요청을 병렬로 보내므로 홈이 채워지는 시간은 가장 느린 요청이 정한다.
    slowest = max(worst_history, worst_new, worst_totals)
    print(f"캐시가 모두 비었을 때 홈 진입 대기 시간 ≈ 가장 느린 요청 {slowest:.0f} ms")
    if slowest < 300:
        print('판정: 캐시 없이도 빠릅니다. 클라이언트 캐시 없이 재진입해도 체감 지연이 없을 것으로 보입니다.')
    elif slowest < 1500:
        print('판정: 캐시가 비었을 때 다소 느립니다. Redis 캐시가 유지되는지(위 Redis 항목)와 함께 보세요.')
    else:
        print('판정: 캐시가 비었을 때 느립니다. 가장 느린 항목의 쿼리를 확인해야 합니다.')


if __name__ == '__main__':
    main()
