import io
import os
import tempfile
import unicodedata
import unittest
import zipfile
from unittest.mock import patch

from PIL import Image

from tools.scanner import cover
from tools.scanner.cover import get_series_cover_fallback, pick_archive_cover_image
from utils.sort_helper import natural_sort_key

_IMG_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')


def _comicinfo(front_cover_index):
    return (
        '<?xml version="1.0"?>'
        '<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<Pages>'
        '<Page Image="0" Type="Story"/>'
        f'<Page Image="{front_cover_index}" Type="FrontCover"/>'
        '</Pages>'
        '</ComicInfo>'
    )


def _pick(entries):
    """entries: {파일명: 바이트}. 스캐너와 같은 방식으로 정렬한 뒤 표지로 고른 파일명을 돌려준다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    with zipfile.ZipFile(buf) as zf:
        img_infos = sorted(
            [i for i in zf.infolist() if i.filename.lower().endswith(_IMG_EXT)],
            key=lambda x: natural_sort_key(x.filename),
        )
        return pick_archive_cover_image(zf, img_infos).filename


class PickArchiveCoverImageTest(unittest.TestCase):
    def test_first_page_when_no_hint(self):
        self.assertEqual(_pick({'002.jpg': b'x', '001.jpg': b'x'}), '001.jpg')

    def test_cover_name_beats_numeric_pages(self):
        self.assertEqual(_pick({'001.jpg': b'x', '002.jpg': b'x', 'cover.jpg': b'x'}), 'cover.jpg')

    def test_cover_name_is_case_insensitive_and_in_subfolder(self):
        self.assertEqual(_pick({'vol1/001.jpg': b'x', 'vol1/Cover.PNG': b'x'}), 'vol1/Cover.PNG')

    def test_korean_cover_name_including_nfd(self):
        self.assertEqual(_pick({'001.jpg': b'x', '표지.jpg': b'x'}), '표지.jpg')
        nfd = unicodedata.normalize('NFD', '표지') + '.jpg'
        self.assertEqual(_pick({'001.jpg': b'x', nfd: b'x'}), nfd)

    def test_partial_name_is_not_a_cover(self):
        self.assertEqual(_pick({'001.jpg': b'x', 'cover_back.jpg': b'x'}), '001.jpg')

    def test_comicinfo_front_cover_wins(self):
        entries = {'001.jpg': b'x', '002.jpg': b'x', '003.jpg': b'x', 'cover.jpg': b'x',
                   'ComicInfo.xml': _comicinfo(2)}
        self.assertEqual(_pick(entries), '003.jpg')

    def test_comicinfo_out_of_range_falls_back_to_name(self):
        entries = {'001.jpg': b'x', 'cover.jpg': b'x', 'ComicInfo.xml': _comicinfo(99)}
        self.assertEqual(_pick(entries), 'cover.jpg')

    def test_broken_comicinfo_falls_back(self):
        entries = {'001.jpg': b'x', 'cover.jpg': b'x', 'ComicInfo.xml': '<ComicInfo><Pages>'}
        self.assertEqual(_pick(entries), 'cover.jpg')


class ScannerUsesPickedCoverTest(unittest.TestCase):
    def test_extracted_cover_comes_from_cover_image(self):
        def png(color):
            out = io.BytesIO()
            Image.new('RGB', (40, 60), color).save(out, 'PNG')
            return out.getvalue()

        with tempfile.TemporaryDirectory() as lib_dir, tempfile.TemporaryDirectory() as covers_dir:
            cbz_path = os.path.join(lib_dir, 'vol01.cbz')
            with zipfile.ZipFile(cbz_path, 'w') as zf:
                zf.writestr('001.png', png((255, 0, 0)))
                zf.writestr('cover.png', png((0, 0, 255)))

            with patch.object(cover, 'get_covers_dir', return_value=covers_dir):
                db_path = get_series_cover_fallback('series', lib_dir, force=True, filename='vol01.cbz',
                                                    file_path=cbz_path, library_id=1)

            with Image.open(os.path.join(covers_dir, db_path)) as img:
                r, g, b = img.convert('RGB').getpixel((10, 10))
            self.assertGreater(b, 200)
            self.assertLess(r, 50)


if __name__ == '__main__':
    unittest.main()
