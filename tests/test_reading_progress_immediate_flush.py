from unittest.mock import patch

from services.reading_progress_service import ReadingProgressService


def test_immediate_flush_persists_and_clears_inmemory_pending():
    payload = {
        'pages_read': 3,
        'is_completed': 0,
        'last_read_at': '2026-08-09 12:00:00',
        'delta': 1,
    }

    with (
        patch('services.reading_progress_service.get_redis_client', return_value=None),
        patch('services.reading_progress_service.redis_acquire_lock', return_value='direct-token'),
        patch('services.reading_progress_service.ReadingProgressRepository.batch_flush_progress_items', return_value=1) as batch_flush,
        patch('services.reading_progress_service.InMemoryProgressBuffer.delete') as delete_pending,
    ):
        persisted = ReadingProgressService._persist_progress_immediately('general', 7, 11, payload)

    assert persisted is True
    batch_flush.assert_called_once_with(
        'general',
        [{**payload, 'user_id': 7, 'book_id': 11}],
    )
    delete_pending.assert_called_once_with('general', 7, 11)


def test_immediate_flush_returns_false_when_write_gate_is_busy():
    with (
        patch('services.reading_progress_service.get_redis_client', return_value=object()),
        patch('services.reading_progress_service.redis_acquire_lock', return_value=None),
        patch('services.reading_progress_service.ReadingProgressRepository.batch_flush_progress_items') as batch_flush,
    ):
        persisted = ReadingProgressService._persist_progress_immediately(
            'general', 7, 11, {'pages_read': 3}
        )

    assert persisted is False
    batch_flush.assert_not_called()