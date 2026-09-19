import os
import sqlite3
import tempfile
import unittest
import zipfile
from unittest.mock import Mock, patch

from repositories.book_metadata_fill import SUMMARY_PLACEHOLDER
from repositories.mariadb import book_scan_repository as mariadb_repository
from repositories.sqlite import book_scan_repository as sqlite_repository
from services.book_scan_service import BookScanService
from tools.scanner import embedded_metadata
from tools.scanner.embedded_metadata import read_embedded_metadata

CONTAINER_XML = (
    '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<rootfiles><rootfile full-path="{path}" media-type="application/oebps-package+xml"/></rootfiles></container>'
)


def _opf(metadata_xml):
    return (
        '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">'
        f'{metadata_xml}</metadata></package>'
    )


def _make_epub(directory, metadata_xml, opf_path='OEBPS/content.opf', container_path=None):
    path = os.path.join(directory, 'book.epub')
    with zipfile.ZipFile(path, 'w') as epub:
        epub.writestr('META-INF/container.xml', CONTAINER_XML.format(path=container_path or opf_path))
        epub.writestr(opf_path, _opf(metadata_xml))
    return path


class EpubMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def _read(self, metadata_xml, **kwargs):
        return read_embedded_metadata(_make_epub(self.temp_dir.name, metadata_xml, **kwargs), 'epub')

    def test_reads_author_publisher_summary_date_and_isbn(self):
        metadata = self._read(
            '<dc:creator opf:role="aut">글 작가</dc:creator>'
            '<dc:creator opf:role="ill">그림 작가</dc:creator>'
            '<dc:publisher>테스트 출판사</dc:publisher>'
            '<dc:description>&lt;p&gt;첫 줄&lt;/p&gt;&lt;p&gt;둘째 줄&lt;/p&gt;</dc:description>'
            '<dc:date>2020-3-5</dc:date>'
            '<dc:identifier opf:scheme="ISBN">978-0-306-40615-7</dc:identifier>'
        )

        self.assertEqual(metadata['author'], '글 작가')
        self.assertEqual(metadata['publisher'], '테스트 출판사')
        self.assertEqual(metadata['summary'], '첫 줄\n둘째 줄')
        self.assertEqual(metadata['release_date'], '2020-03-05')
        self.assertEqual(metadata['isbn'], '9780306406157')

    def test_epub3_role_refinement_and_missing_roles(self):
        with_refines = self._read(
            '<dc:creator id="a1">글</dc:creator><dc:creator id="a2">그림</dc:creator>'
            '<meta property="role" refines="#a1">aut</meta><meta property="role" refines="#a2">ill</meta>'
        )
        without_roles = self._read('<dc:creator>가</dc:creator><dc:creator>나</dc:creator>')

        self.assertEqual(with_refines['author'], '글')
        self.assertEqual(without_roles['author'], '가, 나')

    def test_illustrator_only_does_not_become_the_author(self):
        self.assertNotIn('author', self._read('<dc:creator opf:role="ill">그림 작가</dc:creator>'))

    def test_invalid_isbn_and_bad_date_are_ignored(self):
        metadata = self._read(
            '<dc:identifier>urn:isbn:9780306406158</dc:identifier><dc:date>not a date</dc:date>'
        )

        self.assertNotIn('isbn', metadata)
        self.assertNotIn('release_date', metadata)

    def test_genre_is_never_taken_from_epub_subjects(self):
        self.assertNotIn('genre', self._read('<dc:subject>소설 &gt; 한국소설</dc:subject>'))

    def test_opf_path_escaping_the_archive_is_rejected(self):
        path = os.path.join(self.temp_dir.name, 'evil.epub')
        with zipfile.ZipFile(path, 'w') as epub:
            epub.writestr('META-INF/container.xml', CONTAINER_XML.format(path='../outside.opf'))
            # 멤버 이름 자체가 '../outside.opf'라, 경로 검사가 없으면 실제로 읽혀서 작가가 나온다.
            epub.writestr('../outside.opf', _opf('<dc:creator>침입</dc:creator>'))

        self.assertEqual(read_embedded_metadata(path, 'epub'), {})

    def test_oversized_opf_is_not_read(self):
        path = _make_epub(self.temp_dir.name, '<dc:creator>작가</dc:creator>')
        with patch.object(embedded_metadata, '_MAX_OPF_BYTES', 10):
            self.assertEqual(read_embedded_metadata(path, 'epub'), {})

    def test_broken_or_unsupported_files_return_empty_without_raising(self):
        broken = os.path.join(self.temp_dir.name, 'broken.epub')
        with open(broken, 'wb') as handle:
            handle.write(b'not a zip')

        self.assertEqual(read_embedded_metadata(broken, 'epub'), {})
        self.assertEqual(read_embedded_metadata('/x/book.pdf', 'pdf'), {})
        self.assertEqual(read_embedded_metadata('/x/book.txt', 'txt'), {})


class ComicInfoMetadataTests(unittest.TestCase):
    def test_comicinfo_fields_are_mapped_and_empty_ones_dropped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'book.cbz')
            with zipfile.ZipFile(path, 'w') as cbz:
                cbz.writestr(
                    'ComicInfo.xml',
                    '<ComicInfo><Writer>글 작가</Writer><Penciller>그림 작가</Penciller>'
                    '<Publisher>출판사</Publisher><Summary>줄거리</Summary><Genre>액션, 판타지</Genre>'
                    '<Year>2021</Year><Month>4</Month><Day>2</Day></ComicInfo>',
                )
                cbz.writestr('001.jpg', b'x')

            metadata = read_embedded_metadata(path, 'cbz')

        self.assertEqual(metadata['author'], '글 작가')
        self.assertEqual(metadata['cover_artist'], '그림 작가')
        self.assertEqual(metadata['publisher'], '출판사')
        self.assertEqual(metadata['release_date'], '2021-04-02')
        self.assertIn('액션', metadata['genre'])
        self.assertNotIn('teams', metadata)
        self.assertNotIn('books_lv', metadata)


class NonClosingConnection:
    """저장소가 conn.close()를 부르는 인메모리 테스트 DB를 유지하기 위한 래퍼."""

    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


class SqliteFillEmptyMetadataTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            'CREATE TABLE books (id INTEGER PRIMARY KEY, metadata_locked INTEGER DEFAULT 0, author TEXT, '
            'cover_artist TEXT, teams TEXT, locations TEXT, characters TEXT, books_lv TEXT, publisher TEXT, '
            'summary TEXT, release_date TEXT, genre TEXT, tags TEXT, isbn TEXT, title TEXT)'
        )
        self.addCleanup(self.connection.close)
        patcher = patch.object(
            sqlite_repository.database, 'get_connection', return_value=NonClosingConnection(self.connection)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _insert(self, book_id, **values):
        columns = ['id'] + list(values)
        self.connection.execute(
            f"INSERT INTO books ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            [book_id] + list(values.values()),
        )
        self.connection.commit()

    def _row(self, book_id):
        return dict(self.connection.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone())

    def _fill(self, book_id, fields):
        return sqlite_repository.BookScanRepository.fill_empty_book_metadata('general', book_id, fields)

    def test_fills_only_empty_columns_and_reports_them(self):
        self._insert(1, author='기존 작가', publisher='', summary=None)

        filled = self._fill(1, {'author': '파일 작가', 'publisher': '파일 출판사', 'summary': '파일 줄거리'})

        row = self._row(1)
        self.assertEqual(sorted(filled), ['publisher', 'summary'])
        self.assertEqual(row['author'], '기존 작가')
        self.assertEqual(row['publisher'], '파일 출판사')
        self.assertEqual(row['summary'], '파일 줄거리')

    def test_placeholder_summary_counts_as_empty(self):
        self._insert(1, summary=SUMMARY_PLACEHOLDER)

        self.assertEqual(self._fill(1, {'summary': '진짜 줄거리'}), ['summary'])
        self.assertEqual(self._row(1)['summary'], '진짜 줄거리')

    def test_locked_book_is_never_changed(self):
        self._insert(1, metadata_locked=1, author='')

        self.assertEqual(self._fill(1, {'author': '파일 작가'}), [])
        self.assertEqual(self._row(1)['author'], '')

    def test_unknown_columns_and_blank_values_are_ignored(self):
        self._insert(1, author='')

        self.assertEqual(self._fill(1, {'title': '바뀌면 안 됨', 'author': '   ', 'nope': 'x'}), [])
        row = self._row(1)
        self.assertEqual(row['title'], None)
        self.assertEqual(row['author'], '')

    def test_missing_book_is_a_no_op(self):
        self.assertEqual(self._fill(999, {'author': '파일 작가'}), [])


class FakeMariadbCursor:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self.row


class FakeMariadbConnection:
    def __init__(self, row):
        self.cursor_instance = FakeMariadbCursor(row)
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class MariadbFillEmptyMetadataTests(unittest.TestCase):
    def test_uses_mariadb_placeholders_and_guards_each_assignment(self):
        connection = FakeMariadbConnection({'is_locked': 0, 'author': '', 'publisher': '기존'})
        with patch.object(mariadb_repository.database, 'get_connection', return_value=connection):
            filled = mariadb_repository.BookScanRepository.fill_empty_book_metadata(
                'general', 9, {'author': '파일 작가', 'publisher': '파일 출판사'}
            )

        self.assertEqual(filled, ['author'])
        select_query, select_params = connection.cursor_instance.calls[0]
        update_query, update_params = connection.cursor_instance.calls[1]
        self.assertIn('%s', select_query)
        self.assertNotIn('?', select_query + update_query)
        self.assertEqual(select_params, (9,))
        self.assertIn("author = CASE WHEN COALESCE(TRIM(author), '') = '' THEN %s ELSE author END", update_query)
        self.assertIn('COALESCE(metadata_locked, 0) = 0', update_query)
        self.assertEqual(update_params, ('파일 작가', 9))
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_locked_book_issues_no_update(self):
        connection = FakeMariadbConnection({'is_locked': 1, 'author': ''})
        with patch.object(mariadb_repository.database, 'get_connection', return_value=connection):
            filled = mariadb_repository.BookScanRepository.fill_empty_book_metadata(
                'general', 9, {'author': '파일 작가'}
            )

        self.assertEqual(filled, [])
        self.assertEqual(len(connection.cursor_instance.calls), 1)


class ScanSingleBookEmbeddedFillTests(unittest.TestCase):
    def _scan(self, embedded, fill_side_effect=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'book.epub')
            with open(path, 'wb') as handle:
                handle.write(b'x')
            book = {'id': 5, 'library_id': 1, 'title': 'book', 'series_name': 'S',
                    'file_path': path, 'file_format': 'epub'}
            repository = Mock()
            repository.get_book_basic_info_raw.return_value = book
            repository.fill_empty_book_metadata.side_effect = fill_side_effect or (lambda *_a: ['author'])
            with (
                patch('services.book_scan_service.BookScanRepository', repository),
                patch('services.book_scan_service.merge_local_metadata', return_value={
                    'cover_b64_map': {}, 'author': '', 'publisher': '', 'link': '', 'score': 0,
                    'summary': '', 'release_date': '',
                }),
                patch('services.book_scan_service.get_series_cover_fallback', return_value='1/5.webp'),
                patch('services.book_scan_service.redis_delete_pattern'),
                patch('tools.scanner.embedded_metadata.read_embedded_metadata', return_value=embedded),
            ):
                result = BookScanService.scan_single_book('general', 5)
        return result, repository

    def test_embedded_metadata_is_filled_after_the_sidecar_metadata_is_saved(self):
        (success, message, cover), repository = self._scan({'author': '파일 작가'})

        self.assertTrue(success)
        self.assertEqual(cover, '1/5.webp')
        self.assertIn('파일 내장 메타 1개 채움', message)
        method_names = [call[0] for call in repository.method_calls]
        self.assertLess(
            method_names.index('update_book_scanned_metadata'),
            method_names.index('fill_empty_book_metadata'),
        )
        repository.fill_empty_book_metadata.assert_called_once_with('general', 5, {'author': '파일 작가'})

    def test_nothing_is_filled_when_the_file_has_no_embedded_metadata(self):
        (success, message, _cover), repository = self._scan({})

        self.assertTrue(success)
        self.assertNotIn('파일 내장 메타', message)
        repository.fill_empty_book_metadata.assert_not_called()

    def test_an_embedded_metadata_failure_does_not_fail_the_scan(self):
        def explode(*_args):
            raise RuntimeError('db down')

        (success, message, _cover), _repository = self._scan({'author': '파일 작가'}, explode)

        self.assertTrue(success)
        self.assertNotIn('파일 내장 메타', message)


if __name__ == '__main__':
    unittest.main()
