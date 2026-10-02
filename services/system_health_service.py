# -*- coding: utf-8 -*-
"""
system_health_service.py – 백그라운드 작업의 "계속 실패 중" 상태를 관리자에게 조용히 알리는 공용 저장소

배경: 시리즈 요약 테이블(series_summary) 재생성이 created_at NULL 한 행 때문에 12일 동안
매 스캔마다 실패했는데, 실패가 로그에만 남아 아무도 몰랐다(2026-09 홈 서버). 팝업처럼
요란하게 알리면 금방 무시되므로, 실패 중일 때만 상태를 남기고 다음 성공 때 자동으로 지운다.
관리자에게만 상단 스캔 활동 아이콘의 경고 점 + 팝오버 한 줄로 노출된다.

사용법(새 백그라운드 작업에 붙일 때):
    with SystemHealthService.track('series_summary:general', '시리즈 목록 갱신 (일반 도서)'):
        do_work()          # 예외는 그대로 다시 올라간다 - 호출측 동작은 바뀌지 않음

저장소는 문제 기록 테이블(problem_occurrences, target_type='system')이다 - 스캐너 워커는 웹과
별개 OS 프로세스라 메모리/Redis(미설정 배포 존재)로는 공유가 보장되지 않는다.
(2026-10 이전에는 settings의 SYSTEM_HEALTH_<key> 행이었다 - 마이그레이션 때 옮기고 지운다.)
"""
import time
from contextlib import contextmanager

from services.problem_service import (
    CODE_SYSTEM_TASK_FAILED,
    SEVERITY_ACTION_REQUIRED,
    ProblemService,
    make_group_key,
    to_iso,
)

LEGACY_SETTINGS_PREFIX = 'SYSTEM_HEALTH_'
_TARGET_TYPE = 'system'
_GROUP_KEY = make_group_key(CODE_SYSTEM_TASK_FAILED, 'general')
# /api/system/status는 2초마다 폴링되므로 조회를 짧게 캐시한다.
_ACTIVE_CACHE_TTL = 15.0
_active_cache = {'at': 0.0, 'items': []}


# 전용 스캐너 워커 운영에서 워커가 없을 때 (core.ensure_scanner_worker_running이 기록, 워커가 시작하면 해제)
DEDICATED_WORKER_HEALTH_KEY = 'scanner_worker:dedicated'
DEDICATED_WORKER_HEALTH_LABEL = '스캐너 워커 (전용 프로세스)'


def series_summary_health_key(db_type):
    """시리즈 요약 테이블 재생성용 (key, label) - 호출 지점이 여러 곳이라 한곳에서 만든다."""
    name = {'general': '일반 도서', 'adult': '성인 도서', 'video': '영상 강좌'}.get(db_type, db_type)
    return f'series_summary:{db_type}', f'시리즈 목록 갱신 ({name})'


class SystemHealthService:
    @staticmethod
    @contextmanager
    def track(key, label):
        """블록이 예외 없이 끝나면 성공, 예외면 실패로 기록하고 예외는 그대로 다시 던진다."""
        try:
            yield
        except Exception as e:
            SystemHealthService.record_failure(key, label, e)
            raise
        else:
            SystemHealthService.record_success(key)

    @staticmethod
    def record_failure(key, label, error):
        """작업 실패를 기록한다. 연속 실패 횟수(해결 후 재발 시 1부터)와 최초 실패 시각을 유지한다."""
        ok = ProblemService.report(
            CODE_SYSTEM_TASK_FAILED, _TARGET_TYPE, key,
            db_type='general', severity=SEVERITY_ACTION_REQUIRED, source='system',
            title=str(label), message=str(error), group_key=_GROUP_KEY,
        )
        _active_cache['at'] = 0.0
        return ok

    @staticmethod
    def record_success(key):
        """작업 성공을 기록한다. 실패 상태였다면 경고가 자동으로 사라진다(열린 행이 없으면 쓰기 없음)."""
        if ProblemService.resolve(CODE_SYSTEM_TASK_FAILED, _TARGET_TYPE, key, db_type='general'):
            _active_cache['at'] = 0.0

    @staticmethod
    def get_active_warnings():
        """현재 실패 중인 항목 목록 (관리자 상태 표시용). 조회 실패 시 빈 목록."""
        now = time.time()
        if now - _active_cache['at'] < _ACTIVE_CACHE_TTL:
            return _active_cache['items']
        items = []
        for row in ProblemService.list_open(target_type=_TARGET_TYPE, code=CODE_SYSTEM_TASK_FAILED):
            items.append({
                'key': row['target_id'],
                'label': row.get('title') or row['target_id'],
                'message': row.get('message') or '',
                'first_failed_at': to_iso(row.get('first_seen_ms')),
                'last_failed_at': to_iso(row.get('last_seen_ms')),
                'fail_count': int(row.get('occurrence_count') or 0),
                'last_ok_at': to_iso(row.get('resolved_ms')),
            })
        _active_cache['at'] = now
        _active_cache['items'] = items
        return items
