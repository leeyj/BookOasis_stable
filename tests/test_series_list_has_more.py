import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.series_service import SeriesService


class GetBooksListHasMoreTests(unittest.TestCase):
    """v2.7.6 버그수정: 오디오북/영상처럼 여러 원본 도서 행이 한 시리즈로 묶이는 경우,
    그룹핑 후 개수만으로 has_more를 판정하면 실제로 더 있어도 무한 스크롤이 멈췄다
    (예: 2,846개 중 61개 원본 행을 가져왔는데 58개 시리즈로 묶여 has_more=False가 됨).
    원본 행 개수(limit+1을 채웠는지)로 판정해야 정확하다."""

    def test_has_more_true_when_grouping_collapses_raw_rows(self):
        rows = [{'id': i} for i in range(61)]  # limit(60)+1 raw rows fetched
        collapsed_entries = [{'series_name': str(i)} for i in range(58)]  # 일부가 같은 시리즈로 묶임

        with patch('services.series_service.SeriesRepository.fetch_books_for_grouping', return_value=rows), \
             patch('services.series_service._build_series_entries', return_value=collapsed_entries), \
             patch('services.series_service._sort_entries'):
            series_list, has_more = SeriesService.get_books_list(
                'audiobook', 8, 1, 60, '', 'asc', return_has_more=True
            )

        self.assertTrue(has_more)
        self.assertEqual(len(series_list), 58)

    def test_has_more_false_when_raw_rows_exhausted(self):
        rows = [{'id': i} for i in range(40)]  # limit(60)보다 적게 왔으니 더 없음이 확정
        entries = [{'series_name': str(i)} for i in range(40)]

        with patch('services.series_service.SeriesRepository.fetch_books_for_grouping', return_value=rows), \
             patch('services.series_service._build_series_entries', return_value=entries), \
             patch('services.series_service._sort_entries'):
            series_list, has_more = SeriesService.get_books_list(
                'audiobook', 8, 1, 60, '', 'asc', return_has_more=True
            )

        self.assertFalse(has_more)
        self.assertEqual(len(series_list), 40)

    def test_default_contract_returns_plain_list(self):
        rows = [{'id': i} for i in range(61)]
        entries = [{'series_name': str(i)} for i in range(58)]

        with patch('services.series_service.SeriesRepository.fetch_books_for_grouping', return_value=rows), \
             patch('services.series_service._build_series_entries', return_value=entries), \
             patch('services.series_service._sort_entries'):
            result = SeriesService.get_books_list('audiobook', 8, 1, 60, '', 'asc')

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 58)


if __name__ == '__main__':
    unittest.main()
