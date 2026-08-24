"""공용 UTC 타임스탬프 유틸리티.

기존에는 파일마다 UTC ISO 문자열을 만드는 방식이 달랐다
(예: datetime.utcnow().isoformat() + 'Z' vs datetime.now(timezone.utc).isoformat()).
전자는 'Z' 접미사, 후자는 '+00:00' 오프셋을 붙여 결과 문자열 형태가 달랐으므로
외부에 노출되는 UTC 타임스탬프(webhook 페이로드, 화이트리스트 기록 등)는 이 헬퍼로 통일한다.
"""
from datetime import datetime, timezone


def utc_now_iso():
    """UTC 기준 'YYYY-MM-DDTHH:MM:SS.ffffffZ' 형태의 ISO8601 문자열을 반환한다."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'


def scan_elapsed(start_time):
    """스캔 시작시각(start_time, naive local datetime) 기준으로 지금까지의 경과시간(초)과
    지금 시각의 'YYYY-MM-DD HH:MM:SS' 문자열을 함께 반환한다.
    (scheduler_service.py/cover_scan_service.py에 각각 따로 있던 duration/end_str 계산 중복을 통합)"""
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    return duration, end_time.strftime('%Y-%m-%d %H:%M:%S')
