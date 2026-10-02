"""스캐너 문제 기록 + 대량 사라짐 안전장치 (services/scan_problem_service.py) - 알림센터 4단계.

실제 엔진(_scan_library_internal)을 임시 SQLite DB로 돌려, 휴지통 이동이 보류/진행되는지와
문제 기록이 남고 다음 스캔에서 해제되는지 확인한다.
"""
import os
import shutil
from unittest.mock import patch

from services import scan_problem_service as sps
from tools.scanner import engine
from tools.scanner.path_utils import join_canonical
from test_scanner_stale_update_recovery import _ScanFixture


class GateFixture(_ScanFixture):
    def _add_rows(self, count, series='S'):
        conn = self._connect()
        for i in range(count):
            path = join_canonical(self.series_dir, f'missing_{i:03d}.zip')
            conn.execute(
                "INSERT INTO books (library_id, title, series_name, file_path, file_format, total_pages) VALUES (1, ?, ?, ?, 'zip', 0)",
                (f'm{i}', series, path),
            )
        conn.commit()
        conn.close()

    def _run(self, task=None):
        self._scan(task or self._fake_task())

    def _problems(self, status='open'):
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT code, severity, target_type, target_id, series_key, group_key FROM problem_occurrences WHERE status = ? ORDER BY id",
                (status,),
            ).fetchall()]
        finally:
            conn.close()

    def _trashed(self):
        conn = self._connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM books WHERE is_deleted = 1").fetchone()[0]
        finally:
            conn.close()


class DeletionGateTests(GateFixture):
    def test_few_missing_books_are_trashed_and_noted(self):
        self._insert_existing()
        self._add_rows(2)
        self._run()
        self.assertEqual(self._trashed(), 2)
        problems = self._problems()
        self.assertEqual([p['code'] for p in problems], ['file_missing', 'file_missing'])
        self.assertTrue(all(p['severity'] == 'notice' and p['series_key'] == '1|S' for p in problems))

    def test_mass_missing_with_live_root_is_held_for_confirmation(self):
        self._insert_existing()
        self._add_rows(24)
        self._run()
        self.assertEqual(self._trashed(), 0)
        problems = self._problems()
        self.assertEqual({p['code'] for p in problems}, {'mass_missing'})
        self.assertEqual(len(problems), 24)
        self.assertEqual(problems[0]['group_key'], 'mass_missing|general|1')
        self.assertEqual(problems[0]['severity'], 'action_required')

        # 관리자 확인: 아직 없는 파일만 휴지통으로, 카드는 해제되고 file_missing(참고)로 남는다
        with patch.object(sps, '_library_roots', lambda *_a, **_k: [self.lib_root]):
            result = sps.confirm_trash('mass_missing|general|1')
        self.assertEqual(result, {'trashed': 24, 'reappeared': 0})
        self.assertEqual(self._trashed(), 24)
        self.assertEqual({p['code'] for p in self._problems()}, {'file_missing'})

        # 다음 스캔: 이미 휴지통에 있는 24권은 '새로 사라진' 것이 아니므로 다시 보류/기록되지 않는다
        self._run()
        self.assertEqual({p['code'] for p in self._problems()}, {'file_missing'})
        conn = self._connect()
        counts = conn.execute("SELECT MAX(occurrence_count) FROM problem_occurrences WHERE status = 'open'").fetchone()[0]
        conn.close()
        self.assertEqual(counts, 1)

    def test_root_unreachable_never_trashes_and_clears_after_recovery(self):
        self._insert_existing()
        self._add_rows(3)
        backup = os.path.join(self.temp_dir.name, 'outside_backup')  # 카테고리 밖으로
        shutil.move(self.series_dir, backup)  # 카테고리 루트가 비었다 = 마운트 끊김과 같은 모습
        self._run()
        self.assertEqual(self._trashed(), 0)
        problems = self._problems()
        self.assertEqual([(p['code'], p['target_type']) for p in problems], [('remote_unavailable', 'library')])

        shutil.move(backup, self.series_dir)  # 복구
        self._run()
        codes = [p['code'] for p in self._problems()]
        self.assertNotIn('remote_unavailable', codes)
        self.assertEqual(self._trashed(), 3)  # 이제야 진짜 없는 3권만 휴지통으로

    def test_restored_file_clears_file_missing(self):
        self._insert_existing()
        self._add_rows(1)
        self._run()
        self.assertEqual([p['code'] for p in self._problems()], ['file_missing'])
        with open(join_canonical(self.series_dir, 'missing_000.zip'), 'wb') as handle:
            handle.write(b'zip')
        self._run()
        self.assertEqual(self._problems(), [])

    def test_file_error_is_recorded_then_cleared_when_reprocessed(self):
        self._insert_existing()
        base_task = self._fake_task()

        def failing(root, files, *args, **kwargs):
            res = base_task(root, files, *args, **kwargs)
            res['errors'] = [{'file_path': self.book, 'error_type': 'BadZipFile', 'message': 'bad header'}]
            return res

        self._run(failing)
        problems = self._problems()
        self.assertEqual([(p['code'], p['target_type'], p['series_key']) for p in problems], [('file_corrupt', 'book', '1|S')])
        self._run(base_task)
        self.assertEqual(self._problems(), [])


def test_mass_threshold_needs_ratio_and_count():
    assert not sps.is_mass_missing('general', 1, 19, 19)       # 100%지만 20건 미만
    assert not sps.is_mass_missing('general', 1, 200, 70000)   # 200건이지만 0.3%
    assert sps.is_mass_missing('general', 1, 20, 100)
    assert not sps.is_mass_missing('general', 1, 0, 0)


def test_check_roots(tmp_path):
    empty = tmp_path / 'empty'
    empty.mkdir()
    full = tmp_path / 'full'
    full.mkdir()
    (full / 'a.zip').write_bytes(b'x')
    assert sps.check_roots([str(full)]) == (True, [])
    ok, failures = sps.check_roots([str(full), str(empty), str(tmp_path / 'nope')])
    assert not ok and [why for _p, why in failures] == ['empty', 'not found']
    assert sps.check_roots(['gdrive://abc'])[0]  # 웹 링크 카테고리는 점검 대상 아님


def test_gate_failure_holds_deletions():
    class Broken:
        def execute(self, *_a, **_k):
            raise RuntimeError('db gone')
    with patch.object(sps, 'is_mass_missing', return_value=True):
        assert sps.gate_deletions(Broken(), 'general', 1, {'a'}, {'a': 1}, ['/x'], 0)[:2] == (False, 'root')
