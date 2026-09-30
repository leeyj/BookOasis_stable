"""SystemHealthService: 계속 실패 중인 백그라운드 작업 경고 기록/해제 테스트."""
import unittest
from unittest.mock import patch

from services import system_health_service
from services.system_health_service import SystemHealthService, series_summary_health_key


class _FakeSettings:
    def __init__(self):
        self.rows = {}
        self.writes = 0

    def get_value(self, key):
        return self.rows.get(key)

    def set_value(self, key, value):
        self.writes += 1
        self.rows[key] = value

    def get_settings_by_prefix(self, prefix):
        return {k: v for k, v in self.rows.items() if k.startswith(prefix)}


class SystemHealthServiceTests(unittest.TestCase):
    def setUp(self):
        self.settings = _FakeSettings()
        p = patch.object(system_health_service, 'SettingsRepository', self.settings)
        p.start()
        self.addCleanup(p.stop)
        system_health_service._active_cache['at'] = 0.0
        self.key, self.label = series_summary_health_key('general')

    def _fail(self, message='boom'):
        with self.assertRaises(RuntimeError):
            with SystemHealthService.track(self.key, self.label):
                raise RuntimeError(message)

    def test_success_without_history_writes_nothing(self):
        with SystemHealthService.track(self.key, self.label):
            pass
        self.assertEqual(self.settings.writes, 0)
        self.assertEqual(SystemHealthService.get_active_warnings(), [])

    def test_repeated_failures_accumulate_then_clear_on_success(self):
        self._fail('first')
        self._fail("(1048, \"Column 'latest_added' cannot be null\")")

        warnings = SystemHealthService.get_active_warnings()
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['key'], 'series_summary:general')
        self.assertEqual(warnings[0]['fail_count'], 2)
        self.assertIn('latest_added', warnings[0]['message'])
        self.assertTrue(warnings[0]['first_failed_at'])

        with SystemHealthService.track(self.key, self.label):
            pass
        self.assertEqual(SystemHealthService.get_active_warnings(), [])

    def test_failure_after_success_keeps_last_ok_at(self):
        self._fail()
        with SystemHealthService.track(self.key, self.label):
            pass
        self._fail()
        warning = SystemHealthService.get_active_warnings()[0]
        self.assertTrue(warning['last_ok_at'])
        self.assertEqual(warning['fail_count'], 1)

    def test_storage_error_never_breaks_caller(self):
        def broken(*_args, **_kwargs):
            raise OSError('db down')
        self.settings.get_value = broken
        self.settings.set_value = broken
        self.settings.get_settings_by_prefix = broken
        with SystemHealthService.track(self.key, self.label):
            pass
        self.assertEqual(SystemHealthService.get_active_warnings(), [])


if __name__ == '__main__':
    unittest.main()
