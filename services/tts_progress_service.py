# -*- coding: utf-8 -*-
"""
tts_progress_service.py – 브라우저 TTS 듣기 위치 저장과 읽기↔듣기 위치 동기화

위치는 (챕터, 글자 오프셋, 기준 텍스트 길이, 앵커 문구)로 주고받는다. 어느 쪽을 따를지는
더 최근에 저장된 쪽(latest)으로 정하고, 실제 텍스트 매칭(앵커 탐색/비율 근사)은 텍스트를
가진 클라이언트가 한다 (static/js/viewer/text_position_utils.js).
"""
import time

from repositories.tts_progress_repository import TTSProgressRepository
from services.reading_progress_service import ReadingProgressService

VOICES = {'F1', 'F2', 'F3', 'F4', 'F5', 'M1', 'M2', 'M3', 'M4', 'M5'}
STEPS = {2, 4, 8}
MAX_ANCHOR_CHARS = 200
MAX_INT = 2_000_000_000


def _non_negative_int(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer")
    if number < 0 or number > MAX_INT:
        raise ValueError(f"{name} out of range")
    return number


def _position_from_row(row, kind):
    if not row or not row.get(f'{kind}_updated_ms'):
        return None
    return {
        'chapter_idx': row.get(f'{kind}_chapter') or 0,
        'char_offset': row.get(f'{kind}_offset') or 0,
        'text_len': row.get(f'{kind}_text_len') or 0,
        'anchor': row.get(f'{kind}_anchor') or '',
        'updated_ms': int(row.get(f'{kind}_updated_ms')),
    }


class TTSProgressService:
    @staticmethod
    def validate(payload):
        """요청 본문을 검증해 (kind, position, settings)로 정규화. 잘못된 값은 ValueError."""
        kind = payload.get('kind')
        if kind not in ('listen', 'read'):
            raise ValueError("kind must be 'listen' or 'read'")
        anchor = payload.get('anchor') or ''
        if not isinstance(anchor, str):
            raise ValueError("anchor must be a string")
        position = {
            'chapter': _non_negative_int(payload.get('chapter_idx', 0), 'chapter_idx'),
            'offset': _non_negative_int(payload.get('char_offset', 0), 'char_offset'),
            'text_len': _non_negative_int(payload.get('text_len', 0), 'text_len'),
            'anchor': anchor[:MAX_ANCHOR_CHARS],
        }
        settings = {}
        if kind == 'listen':
            voice = payload.get('voice')
            if voice is not None:
                if voice not in VOICES:
                    raise ValueError("invalid voice")
                settings['voice'] = voice
            steps = payload.get('steps')
            if steps is not None:
                steps = _non_negative_int(steps, 'steps')
                if steps not in STEPS:
                    raise ValueError("invalid steps")
                settings['steps'] = steps
            speed = payload.get('speed')
            if speed is not None:
                try:
                    speed = float(speed)
                except (TypeError, ValueError):
                    raise ValueError("speed must be a number")
                if not 0.5 <= speed <= 2.0:
                    raise ValueError("speed out of range")
                settings['speed'] = speed
        return kind, position, settings

    @staticmethod
    def save(db_type, book_id, user_id, payload, now_ms=None):
        kind, position, settings = TTSProgressService.validate(payload)
        position['updated_ms'] = int(now_ms if now_ms is not None else time.time() * 1000)
        TTSProgressRepository.save(db_type, book_id, user_id, kind, position, settings)
        return position['updated_ms']

    @staticmethod
    def get_sync_state(db_type, book_id, user_id):
        """{listen, read, legacy, latest, settings}.
        latest: 더 최근에 저장된 쪽. 아직 세밀한 읽기 위치(read)가 없으면 기존 뷰어 진도(legacy:
        TXT 4000자 페이지 / EPUB 챕터 단위)를 대신 쓴다 — 이 기능 이전에 읽던 책도 이어지게."""
        row = TTSProgressRepository.get(db_type, book_id, user_id)
        listen = _position_from_row(row, 'listen')
        read = _position_from_row(row, 'read')

        legacy = None
        if read is None:
            try:
                state = ReadingProgressService.get_progress_state(db_type, book_id, user_id)
            except Exception:
                state = None
            if state:
                epub_index = (state.get('epub_session') or {}).get('index')
                pages_read = state.get('pages_read') or 0
                if pages_read > 0 or epub_index is not None:
                    legacy = {
                        'pages_read': pages_read,
                        'total_pages': state.get('total_pages') or 0,
                        'epub_index': epub_index,
                    }

        if listen and read:
            latest = 'listen' if listen['updated_ms'] > read['updated_ms'] else 'read'
        elif listen:
            latest = 'listen'
        elif read:
            latest = 'read'
        elif legacy:
            latest = 'legacy'
        else:
            latest = None

        settings = None
        if row and row.get('voice'):
            settings = {'voice': row.get('voice'), 'steps': row.get('steps'), 'speed': row.get('speed')}

        return {'listen': listen, 'read': read, 'legacy': legacy, 'latest': latest, 'settings': settings}
