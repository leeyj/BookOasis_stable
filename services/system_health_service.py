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

저장소는 settings 테이블(SYSTEM_HEALTH_<key>)이다 - 스캐너 워커는 웹과 별개 OS 프로세스라
메모리/Redis(미설정 배포 존재)로는 공유가 보장되지 않는다.
"""
import json
import time
from contextlib import contextmanager
from datetime import datetime

from repositories.settings_repository import SettingsRepository

_KEY_PREFIX = 'SYSTEM_HEALTH_'
_MESSAGE_MAX_LEN = 300
# /api/system/status는 2초마다 폴링되므로 settings 조회를 짧게 캐시한다.
_ACTIVE_CACHE_TTL = 15.0
_active_cache = {'at': 0.0, 'items': []}


def _now_str():
    # 타임존 오프셋을 붙여 저장한다(예: 2026-09-29T13:17:34+00:00). 서버가 UTC로 도는 환경에서
    # 오프셋 없는 문자열을 내려주면 브라우저가 로컬(KST) 시각으로 읽어 "N시간 전"이 9시간 어긋났다.
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _load(key):
    try:
        raw = SettingsRepository.get_value(_KEY_PREFIX + key)
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _save(key, record):
    SettingsRepository.set_value(_KEY_PREFIX + key, json.dumps(record, ensure_ascii=False))
    _active_cache['at'] = 0.0


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
        """작업 실패를 기록한다. 연속 실패 횟수와 최초 실패 시각을 유지한다."""
        try:
            record = _load(key)
            now = _now_str()
            if record.get('status') != 'failed':
                record['first_failed_at'] = now
                record['fail_count'] = 0
            record.update({
                'status': 'failed',
                'label': str(label),
                'last_failed_at': now,
                'fail_count': int(record.get('fail_count') or 0) + 1,
                'message': str(error)[:_MESSAGE_MAX_LEN],
            })
            _save(key, record)
        except Exception as e:
            print(f"[SystemHealth] record_failure '{key}' failed: {e}")

    @staticmethod
    def record_success(key):
        """작업 성공을 기록한다. 실패 상태였다면 경고가 자동으로 사라진다."""
        try:
            record = _load(key)
            if not record:
                # 한 번도 실패한 적 없는 작업은 성공할 때마다 settings에 쓸 필요가 없다.
                return
            _save(key, {
                'status': 'ok',
                'label': record.get('label', ''),
                'last_ok_at': _now_str(),
            })
        except Exception as e:
            print(f"[SystemHealth] record_success '{key}' failed: {e}")

    @staticmethod
    def get_active_warnings():
        """현재 실패 중인 항목 목록 (관리자 상태 표시용). 조회 실패 시 빈 목록."""
        now = time.time()
        if now - _active_cache['at'] < _ACTIVE_CACHE_TTL:
            return _active_cache['items']
        items = []
        try:
            rows = SettingsRepository.get_settings_by_prefix(_KEY_PREFIX)
            for full_key, raw in sorted(rows.items()):
                try:
                    record = json.loads(raw) if raw else {}
                except (TypeError, ValueError):
                    continue
                if record.get('status') != 'failed':
                    continue
                items.append({
                    'key': full_key[len(_KEY_PREFIX):],
                    'label': record.get('label') or full_key[len(_KEY_PREFIX):],
                    'message': record.get('message', ''),
                    'first_failed_at': record.get('first_failed_at', ''),
                    'last_failed_at': record.get('last_failed_at', ''),
                    'fail_count': int(record.get('fail_count') or 0),
                    'last_ok_at': record.get('last_ok_at', ''),
                })
        except Exception as e:
            print(f"[SystemHealth] get_active_warnings failed: {e}")
        _active_cache['at'] = now
        _active_cache['items'] = items
        return items
