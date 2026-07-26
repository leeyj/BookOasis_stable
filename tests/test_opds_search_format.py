import unittest
from unittest.mock import patch

from services.opds_service import search_books_entries


class OpdsSearchFormatTest(unittest.TestCase):
    def setUp(self):
        self.books = [
            {
                'id': 1,
                'title': '도굴왕 1권',
                'series_name': '도굴왕',
                'author': '산지직송',
                'file_path': '/books/도굴왕.cbz',
                'file_format': 'cbz',
                'cover_image': None,
                'summary': '',
            },
            {
                'id': 2,
                'title': '도굴왕 소설',
                'series_name': '도굴왕',
                'author': '산지직송',
                'file_path': '/books/도굴왕.epub',
                'file_format': 'epub',
                'cover_image': None,
                'summary': '',
            },
        ]

    def build_entries(self, urn_prefix='general'):
        with patch(
            'services.opds_service.OpdsRepository.search_books_like',
            return_value=(self.books, len(self.books)),
        ):
            entries, total = search_books_entries(
                'general', '도굴왕', '/opds/download/general', urn_prefix
            )
        self.assertEqual(total, 2)
        return entries

    def test_search_entries_expose_comic_and_epub_labels(self):
        entries = self.build_entries()

        self.assertEqual(entries[0]['title'], '[만화] 도굴왕 1권')
        self.assertEqual(entries[0]['format_term'], 'CBZ')
        self.assertTrue(entries[0]['summary'].startswith('형식: 만화'))
        self.assertEqual(entries[1]['title'], '[EPUB] 도굴왕 소설')
        self.assertEqual(entries[1]['format_term'], 'EPUB')


if __name__ == '__main__':
    unittest.main()