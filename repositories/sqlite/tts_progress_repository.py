# -*- coding: utf-8 -*-
"""
tts_progress_repository.py – SQLite 전용 브라우저 TTS 듣기 위치 / 읽기↔듣기 동기화 위치 데이터 액세스 레이어

한 행에 듣기(listen_*)와 읽기(read_*) 위치를 따로 둔다. 위치는 조각 번호가 아니라
(챕터, 글자 오프셋, 기준 텍스트 길이, 앵커 문구)라서 분할 방식이 바뀌어도 어긋나지 않고,
받는 쪽이 앵커를 못 찾으면 오프셋/길이 비율로 근사한다. 뷰어 진도(user_progress)와는 분리해
기존 진도 파이프라인을 건드리지 않는다. 시각은 DB 시간대 차이가 없는 epoch ms.
"""
import database

KINDS = ('listen', 'read')
_POSITION_FIELDS = ('chapter', 'offset', 'text_len', 'anchor', 'updated_ms')


class TTSProgressRepository:
    @staticmethod
    def get(db_type, book_id, user_id):
        """도서/사용자의 듣기·읽기 위치 행을 dict로 반환 (없으면 None)"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tts_progress WHERE book_id = ? AND user_id = ?",
                (book_id, user_id),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def save(db_type, book_id, user_id, kind, position, settings=None):
        """kind('listen'|'read') 칸만 갱신하는 UPSERT. 다른 kind의 위치는 보존된다.
        position: {chapter, offset, text_len, anchor, updated_ms}, settings: {voice, steps, speed} (listen만)"""
        if kind not in KINDS:
            raise ValueError(f"invalid kind: {kind}")
        columns = [f"{kind}_{field}" for field in _POSITION_FIELDS]
        values = [position.get(field) for field in _POSITION_FIELDS]
        if kind == 'listen' and settings:
            for key in ('voice', 'steps', 'speed'):
                if settings.get(key) is not None:
                    columns.append(key)
                    values.append(settings[key])
        col_list = ', '.join(['book_id', 'user_id'] + columns)
        placeholders = ', '.join(['?'] * (len(columns) + 2))
        updates = ', '.join(f"{col} = excluded.{col}" for col in columns)
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"INSERT INTO tts_progress ({col_list}) VALUES ({placeholders}) ON CONFLICT(book_id, user_id) DO UPDATE SET {updates}",
                tuple([book_id, user_id] + values),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
