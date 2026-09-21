import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import lazy_scanner


class LazyCoverResizeExclusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.covers = os.path.join(self.tmp.name, 'covers')
        os.makedirs(os.path.join(self.covers, '1'))
        self.progress = os.path.join(self.tmp.name, 'progress.txt')

    def tearDown(self):
        self.tmp.cleanup()

    def _img(self, rel, size, fmt):
        path = os.path.join(self.covers, rel)
        Image.new('RGB', size, (10, 20, 30)).save(path, fmt)
        return path

    def _run(self):
        with patch('services.cover_storage_service.get_covers_dir', return_value=self.covers), \
             patch.object(lazy_scanner, 'COVER_RESIZE_PROGRESS_FILE', self.progress), \
             patch.object(lazy_scanner, '_load_lazy_scan_cover_resize_batch_size', return_value=100):
            lazy_scanner.stop_requested = False
            lazy_scanner.run_lazy_cover_resize()

    def _size(self, path):
        with Image.open(path) as im:
            return im.size

    def test_boss_key_image_untouched_but_cover_and_banner_handled(self):
        fake = self._img('fake_screen.png', (2551, 1036), 'PNG')
        cover = self._img(os.path.join('1', 'cover.webp'), (1000, 1400), 'WEBP')
        banner = self._img(os.path.join('1', 'banner_abc.webp'), (1500, 600), 'WEBP')
        big_banner = self._img(os.path.join('1', 'banner_big.webp'), (3000, 1400), 'WEBP')

        self._run()

        self.assertEqual(self._size(fake), (2551, 1036))                 # 위장 화면은 원본 유지
        self.assertLessEqual(self._size(cover)[0], 480)                  # 표지는 축소
        self.assertEqual(self._size(banner), (1500, 600))                # 배너 상한(1600x700) 이내면 유지
        self.assertLessEqual(self._size(big_banner)[0], 1600)            # 초과분은 배너 상한으로 축소
        self.assertGreater(self._size(big_banner)[0], 480)

    def test_same_name_in_subfolder_is_still_a_cover(self):
        sub = self._img(os.path.join('1', 'fake_screen.png'), (1000, 1400), 'PNG')
        self._run()
        self.assertLessEqual(self._size(sub)[0], 480)


if __name__ == '__main__':
    unittest.main()
