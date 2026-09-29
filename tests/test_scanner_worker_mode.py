import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.process_helper import should_enable_embedded_scanner_worker


class ScannerWorkerModeTests(unittest.TestCase):
    @staticmethod
    def _load_core_worker_module():
        core_path = Path(__file__).resolve().parents[1] / 'core.py'
        spec = importlib.util.spec_from_file_location('_core_worker_mode_test', core_path)
        if spec is None or spec.loader is None:
            raise RuntimeError('core.py 모듈 스펙을 만들 수 없습니다.')
        module = importlib.util.module_from_spec(spec)
        dotenv = types.ModuleType('dotenv')
        setattr(dotenv, 'load_dotenv', lambda: None)
        with patch.dict(os.environ, {'BOOKOASIS_IS_WORKER': 'true'}), \
                patch.dict(sys.modules, {'dotenv': dotenv}):
            spec.loader.exec_module(module)
        return module

    def test_embedded_worker_is_disabled_by_default_in_docker(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch('utils.process_helper.os.path.exists', return_value=True):
            self.assertFalse(should_enable_embedded_scanner_worker())

    def test_embedded_worker_is_enabled_by_default_outside_docker(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch('utils.process_helper.os.path.exists', return_value=False):
            self.assertTrue(should_enable_embedded_scanner_worker())

    def test_explicit_true_overrides_docker_default(self):
        with patch.dict(os.environ, {'BOOKOASIS_ENABLE_EMBEDDED_WORKER': 'true'}, clear=True), \
                patch('utils.process_helper.os.path.exists', return_value=True):
            self.assertTrue(should_enable_embedded_scanner_worker())

    def test_explicit_false_overrides_non_docker_default(self):
        with patch.dict(os.environ, {'BOOKOASIS_ENABLE_EMBEDDED_WORKER': 'false'}, clear=True), \
                patch('utils.process_helper.os.path.exists', return_value=False):
            self.assertFalse(should_enable_embedded_scanner_worker())

    def test_ensure_does_not_probe_or_spawn_when_embedded_worker_is_disabled(self):
        core = self._load_core_worker_module()
        with patch.object(core, 'should_enable_embedded_scanner_worker', return_value=False), \
                patch.object(core, 'is_scanner_worker_running_os') as is_running, \
                patch.object(core, 'start_scanner_worker_process') as start_worker:
            core.ensure_scanner_worker_running()

        is_running.assert_not_called()
        start_worker.assert_not_called()

    def test_ensure_keeps_existing_recovery_when_embedded_worker_is_enabled(self):
        core = self._load_core_worker_module()
        with patch.object(core, 'should_enable_embedded_scanner_worker', return_value=True), \
                patch.object(core, 'is_scanner_worker_running_os', return_value=False), \
                patch.object(core, 'start_scanner_worker_process') as start_worker:
            core.ensure_scanner_worker_running()

        start_worker.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
