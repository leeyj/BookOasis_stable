import os
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from repositories.book_scan_repository import BookScanRepository
from services import book_scan_service
from services.book_scan_service import BookScanService
from services.scanner_queue import _process_batch_book_scan
from tools import lazy_scanner


def _write_cover(covers_dir, relative_path, mtime=None):
    path = os.path.join(covers_dir, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as cover_file:
        cover_file.write(b'cover')
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


class ScanDocumentBooksTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.covers_dir = self.temp_dir.name
        self.books = {}
        self.addCleanup(self.temp_dir.cleanup)

    def _run(self, book_ids, subprocess_side_effect, task_id=None):
        with (
            patch.object(BookScanRepository, 'get_book_basic_info_raw',
                         side_effect=lambda _db, book_id: self.books[book_id]),
            patch.object(BookScanRepository, 'update_book_scanned_metadata') as sync_series_cover,
            patch('services.book_scan_service.subprocess.run', side_effect=subprocess_side_effect) as run_process,
            patch('services.cover_storage_service.get_covers_dir', return_value=self.covers_dir),
            patch('services.book_scan_service.redis_delete_pattern') as purge_cache,
        ):
            result = BookScanService.scan_document_books('general', book_ids, task_id=task_id)
        return result, run_process, sync_series_cover, purge_cache

    def test_runs_one_forced_isolated_process_and_reports_refreshed_covers(self):
        for book_id in (41, 42):
            _write_cover(self.covers_dir, f'3/{book_id}.webp', mtime=1000)
            self.books[book_id] = {'id': book_id, 'series_name': 'Example', 'cover_image': f'3/{book_id}.webp'}

        def refresh_covers(*_args, **_kwargs):
            for book_id in (41, 42):
                _write_cover(self.covers_dir, f'3/{book_id}.webp', mtime=2000)
            return types.SimpleNamespace(returncode=0)

        (success, message, covers), run_process, sync_series_cover, purge_cache = self._run(
            [41, 42, 41], refresh_covers, task_id=88
        )

        self.assertTrue(success)
        self.assertIn('표지 추출 2/2권', message)
        self.assertEqual(covers, {41: '3/41.webp', 42: '3/42.webp'})
        self.assertEqual(run_process.call_count, 1)
        command = run_process.call_args.args[0]
        self.assertEqual(command[command.index('--book-ids') + 1:command.index('--db-type')], ['41', '42'])
        self.assertIn('--force-document-covers', command)
        self.assertEqual(command[command.index('--task-id') + 1], '88')
        self.assertIsNotNone(run_process.call_args.kwargs['timeout'])
        self.assertEqual(sync_series_cover.call_count, 2)
        self.assertTrue(purge_cache.called)

    def test_an_untouched_existing_cover_is_not_reported_as_extracted(self):
        _write_cover(self.covers_dir, '3/41.webp', mtime=1000)
        self.books[41] = {'id': 41, 'series_name': 'Example', 'cover_image': '3/41.webp'}

        (success, message, covers), _run, sync_series_cover, _purge = self._run(
            [41], lambda *_a, **_k: types.SimpleNamespace(returncode=0)
        )

        self.assertFalse(success)
        self.assertEqual(covers, {41: None})
        self.assertIn('0/1권', message)
        sync_series_cover.assert_not_called()

    def test_a_cover_created_for_a_book_that_had_none_counts_as_extracted(self):
        self.books[43] = {'id': 43, 'series_name': 'Example', 'cover_image': None}

        def create_cover(*_args, **_kwargs):
            _write_cover(self.covers_dir, '3/43.webp')
            self.books[43] = {'id': 43, 'series_name': 'Example', 'cover_image': '3/43.webp'}
            return types.SimpleNamespace(returncode=0)

        (success, _message, covers), _run, _sync, _purge = self._run([43], create_cover)

        self.assertTrue(success)
        self.assertEqual(covers, {43: '3/43.webp'})

    def test_timeout_is_reported_and_unfinished_books_fail(self):
        _write_cover(self.covers_dir, '3/41.webp', mtime=1000)
        self.books[41] = {'id': 41, 'series_name': 'Example', 'cover_image': '3/41.webp'}

        def hang(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd='lazy_scanner', timeout=1)

        (success, message, covers), _run, _sync, _purge = self._run([41], hang)

        self.assertFalse(success)
        self.assertEqual(covers, {41: None})
        self.assertIn('제한 시간', message)

    def test_invalid_input_never_starts_a_process(self):
        with patch('services.book_scan_service.subprocess.run') as run_process:
            self.assertFalse(BookScanService.scan_document_books('general', [])[0])
            self.assertFalse(BookScanService.scan_document_books('video', [1])[0])
        run_process.assert_not_called()

    def test_timeout_grows_with_book_count_but_is_capped(self):
        self.assertLess(book_scan_service._document_scan_timeout(1), book_scan_service._document_scan_timeout(10))
        self.assertEqual(
            book_scan_service._document_scan_timeout(10_000),
            book_scan_service._DOCUMENT_SCAN_MAX_TIMEOUT_SECONDS,
        )


class SingleBookPdfScanTests(unittest.TestCase):
    def test_pdf_immediate_scan_waits_for_the_isolated_scan_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = os.path.join(temp_dir, 'book.pdf')
            with open(pdf_path, 'wb') as pdf_file:
                pdf_file.write(b'%PDF-1.4')
            book = {'id': 7, 'library_id': 1, 'title': 'book', 'series_name': 'S',
                    'file_path': pdf_path, 'file_format': 'pdf'}
            with (
                patch.object(BookScanRepository, 'get_book_basic_info_raw', return_value=book),
                patch.object(BookScanService, 'scan_document_books',
                             return_value=(True, 'PDF 표지 스캔 완료 · 표지 추출 1/1권', {7: '1/7.webp'})) as scan_documents,
                patch('services.book_scan_service.subprocess.Popen') as popen,
            ):
                success, message, cover = BookScanService.scan_single_book('general', 7)

        self.assertTrue(success)
        self.assertEqual(cover, '1/7.webp')
        self.assertIn('book.pdf', message)
        scan_documents.assert_called_once_with('general', [7])
        popen.assert_not_called()


class LazyScannerForceTargetsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        _write_cover(self.temp_dir.name, '3/ok.webp')
        patcher = patch('services.cover_storage_service.get_covers_dir', return_value=self.temp_dir.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _book(self, book_id, file_format, locked=0, cover='3/ok.webp'):
        # 후보 선별이 실제 파일 존재까지 확인하므로 임시 파일을 만든다.
        file_path = os.path.join(self.temp_dir.name, f'{book_id}.{file_format}')
        with open(file_path, 'wb') as book_file:
            book_file.write(b'x')
        return {
            'id': book_id, 'file_path': file_path, 'series_name': 'S',
            'file_format': file_format, 'cover_image': cover, 'library_id': 3,
            'total_pages': 10, 'has_offsets': 1, 'metadata_locked': locked,
        }

    def _target_ids(self, books, force_ids):
        targets = lazy_scanner._build_scan_targets(
            'general', books, {3: False}, force_cover_book_ids=force_ids
        )
        return [book['id'] for book, _offset_only in targets]

    def test_forced_document_is_included_even_with_a_valid_cover(self):
        books = [self._book(1, 'pdf'), self._book(2, 'pdf')]

        self.assertEqual(self._target_ids(books, []), [])  # 기존 동작: 표지가 있으면 건너뜀
        self.assertEqual(self._target_ids(books, [1]), [1])

    def test_force_never_applies_to_locked_or_non_document_books(self):
        books = [self._book(1, 'pdf', locked=1), self._book(2, 'cbz'), self._book(3, 'epub')]

        self.assertEqual(self._target_ids(books, [1, 2, 3]), [3])

    def test_valid_cover_file_check(self):
        self.assertTrue(lazy_scanner._has_valid_cover_file('3/ok.webp'))
        self.assertFalse(lazy_scanner._has_valid_cover_file('3/missing.webp'))
        self.assertFalse(lazy_scanner._has_valid_cover_file('NO_COVER'))
        self.assertFalse(lazy_scanner._has_valid_cover_file(None))


class BatchScanGroupsPdfTests(unittest.TestCase):
    def _run(self, books, document_result):
        queue = Mock()
        lookup = Mock(side_effect=lambda _db, book_id: books[book_id])
        scan_single = Mock(return_value=(True, '완료', None))
        scan_documents = Mock(return_value=document_result)
        update_stage = Mock()
        repository_module = types.ModuleType('repositories.book_scan_repository')
        repository_module.BookScanRepository = types.SimpleNamespace(get_book_basic_info_raw=lookup)
        service_module = types.ModuleType('services.book_scan_service')
        service_module.BookScanService = types.SimpleNamespace(
            scan_single_book=scan_single, scan_document_books=scan_documents
        )
        queue_module = types.ModuleType('repositories.scanner_queue_repository')
        queue_module.ScannerQueueRepository = types.SimpleNamespace(update_task_stage=update_stage)
        outcome = None
        with patch.dict('sys.modules', {
            'repositories.book_scan_repository': repository_module,
            'services.book_scan_service': service_module,
            'repositories.scanner_queue_repository': queue_module,
        }):
            try:
                _process_batch_book_scan(queue, task_id=5, db_type='general', book_ids=list(books))
            except RuntimeError as error:
                outcome = error
        return outcome, scan_single, scan_documents, [c.args[1] for c in update_stage.call_args_list]

    def test_pdfs_are_scanned_together_and_others_one_by_one(self):
        books = {
            1: {'title': 'A', 'file_format': 'pdf', 'file_path': '/x/a.pdf'},
            2: {'title': 'B', 'file_format': 'cbz', 'file_path': '/x/b.cbz'},
            3: {'title': 'C', 'file_format': 'pdf', 'file_path': '/x/c.pdf'},
        }

        outcome, scan_single, scan_documents, stages = self._run(
            books, (True, 'ok', {1: '1/1.webp', 3: '1/3.webp'})
        )

        self.assertIsNone(outcome)
        scan_documents.assert_called_once_with('general', [1, 3], task_id=5)
        scan_single.assert_called_once_with('general', 2)
        self.assertEqual(stages[-1], '선택 도서 스캔 완료 · 성공 3/3, 실패 0')

    def test_a_pdf_without_a_new_cover_counts_as_a_failure(self):
        books = {
            1: {'title': 'A', 'file_format': 'pdf', 'file_path': '/x/a.pdf'},
            2: {'title': 'B', 'file_format': 'pdf', 'file_path': '/x/b.pdf'},
        }

        outcome, _scan_single, _scan_documents, stages = self._run(
            books, (False, 'partial', {1: '1/1.webp', 2: None})
        )

        self.assertIsInstance(outcome, RuntimeError)
        self.assertIn('성공 1/2, 실패 1', stages[-1])
        self.assertIn('B: PDF 표지를 추출하지 못했습니다.', str(outcome))


if __name__ == '__main__':
    unittest.main()
