import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import mcp_server


class SearchBooksTests(unittest.TestCase):
    def test_sort_forwarded_and_limit_trimmed(self):
        rows = [{'series_name': str(i)} for i in range(6)]  # 서비스는 limit+1건 반환
        with patch('services.series_service.SeriesService.get_books_list', return_value=rows) as m:
            out = mcp_server._search_books_impl('', 'general', 'all', '', '', 5, 'date_desc')
        self.assertEqual(m.call_args.kwargs['sort'], 'date_desc')
        self.assertEqual(out['total_returned'], 5)
        self.assertEqual(len(out['series']), 5)

    def test_invalid_sort_rejected(self):
        with self.assertRaises(ValueError):
            mcp_server._search_books_impl('', 'general', 'all', '', '', 5, 'bogus')

    def test_video_rejected(self):
        with self.assertRaises(ValueError):
            mcp_server._search_books_impl('', 'video', 'all', '', '', 5, 'asc')


class RandomBookTests(unittest.TestCase):
    def test_index_to_page(self):
        with patch('services.series_service.SeriesService.get_books_totals', return_value={'total_series_count': 10}), \
             patch('random.randint', return_value=7), \
             patch('services.series_service.SeriesService.get_books_list', return_value=[{'a': 1}, {'a': 2}]) as m:
            out = mcp_server._get_random_book_impl('general', 'all')
        self.assertEqual(m.call_args.kwargs['page'], 8)
        self.assertEqual(out['series'], {'a': 1})

    def test_empty_library(self):
        with patch('services.series_service.SeriesService.get_books_totals', return_value={'total_series_count': 0}):
            self.assertIsNone(mcp_server._get_random_book_impl('general', 'all')['series'])

    def test_out_of_range_retries_first_page(self):
        with patch('services.series_service.SeriesService.get_books_totals', return_value={'total_series_count': 10}), \
             patch('random.randint', return_value=9), \
             patch('services.series_service.SeriesService.get_books_list', side_effect=[[], [{'a': 1}]]) as m:
            out = mcp_server._get_random_book_impl('general', 'all')
        self.assertEqual(m.call_count, 2)
        self.assertEqual(out['series'], {'a': 1})


if __name__ == '__main__':
    unittest.main()
