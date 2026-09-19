import os
import random
import tempfile
import unittest
from unittest.mock import patch

from tools.scanner import folder_image
from tools.scanner.folder_image import (
    COMMON_BANNER_NAMES,
    COMMON_COVER_NAMES,
    IMAGE_EXTENSIONS,
    clear_folder_listing_cache,
    find_common_banner,
    find_common_cover,
    find_individual_cover,
)


def _touch(folder, name, content=b'x'):
    with open(os.path.join(folder, name), 'wb') as handle:
        handle.write(content)


def _old_find_common_cover(folder_path):
    """이전 구현(후보 이름마다 os.path.exists) - 소문자 이름 폴더에서의 결과가 그대로인지 비교하는 기준."""
    for cand in COMMON_COVER_NAMES:
        cand_path = os.path.join(folder_path, cand)
        if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
            return cand_path
    return None


def _old_find_individual_cover(folder_path, filename):
    base_name, _ = os.path.splitext(filename)
    for ext in IMAGE_EXTENSIONS:
        cand_path = os.path.join(folder_path, base_name + ext)
        if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
            return cand_path
    return None


class FolderImageLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder = self.temp_dir.name
        self.addCleanup(self.temp_dir.cleanup)
        clear_folder_listing_cache()
        self.addCleanup(clear_folder_listing_cache)

    def test_common_cover_is_found_regardless_of_letter_case(self):
        _touch(self.folder, 'Cover.JPG')

        found = find_common_cover(self.folder)

        self.assertEqual(os.path.basename(found), 'Cover.JPG')

    def test_common_cover_keeps_the_priority_order_of_candidate_names(self):
        _touch(self.folder, 'folder.jpg')
        _touch(self.folder, 'Cover.PNG')

        # COMMON_COVER_NAMES에서 cover.png가 folder.jpg보다 앞선다.
        self.assertEqual(os.path.basename(find_common_cover(self.folder)), 'Cover.PNG')

    def test_an_exact_lowercase_name_wins_over_a_differently_cased_duplicate(self):
        # 대소문자를 구분하는 파일 시스템(리눅스)을 흉내 낸다 - Windows에서는 두 파일을 동시에 만들 수 없다.
        with patch.object(folder_image.os, 'listdir', return_value=['COVER.JPG', 'cover.jpg', 'Cover.jpg']):
            mapping = folder_image._folder_file_map('/some/folder')

        self.assertEqual(mapping['cover.jpg'], 'cover.jpg')

    def test_an_empty_file_is_skipped_in_favor_of_the_next_candidate(self):
        _touch(self.folder, 'cover.jpg', b'')
        _touch(self.folder, 'Folder.png')

        self.assertEqual(os.path.basename(find_common_cover(self.folder)), 'Folder.png')

    def test_individual_cover_matches_the_book_name_and_extension_case_insensitively(self):
        _touch(self.folder, 'Volume 01.JPG')

        found = find_individual_cover(self.folder, 'Volume 01.cbz')

        self.assertEqual(os.path.basename(found), 'Volume 01.JPG')
        self.assertIsNone(find_individual_cover(self.folder, 'Volume 02.cbz'))

    def test_banner_lookup_is_case_insensitive_too(self):
        _touch(self.folder, 'Banner.PNG')

        self.assertEqual(os.path.basename(find_common_banner(self.folder)), 'Banner.PNG')

    def test_missing_or_invalid_folders_return_none_without_raising(self):
        self.assertIsNone(find_common_cover(os.path.join(self.folder, 'nope')))
        self.assertIsNone(find_common_cover(''))
        self.assertIsNone(find_individual_cover(self.folder, ''))
        self.assertIsNone(find_common_cover(self.folder))  # 빈 폴더

    def test_lowercase_folders_give_the_same_answer_as_the_old_implementation(self):
        rng = random.Random(7)
        book_names = ['vol1.cbz', 'vol2.zip', 'my book.epub']
        for _ in range(60):
            with tempfile.TemporaryDirectory() as folder:
                for name in rng.sample(list(COMMON_COVER_NAMES) + [
                    b + ext for b in ('vol1', 'vol2', 'my book') for ext in IMAGE_EXTENSIONS
                ], k=rng.randint(0, 6)):
                    _touch(folder, name, b'x' if rng.random() > 0.15 else b'')
                clear_folder_listing_cache()

                self.assertEqual(find_common_cover(folder), _old_find_common_cover(folder))
                for book in book_names:
                    self.assertEqual(
                        find_individual_cover(folder, book), _old_find_individual_cover(folder, book)
                    )

    def test_all_lookups_in_one_folder_read_the_directory_only_once(self):
        _touch(self.folder, 'Cover.JPG')
        _touch(self.folder, 'vol1.png')

        with patch.object(folder_image.os, 'listdir', wraps=os.listdir) as listdir:
            find_common_cover(self.folder)
            find_individual_cover(self.folder, 'vol1.cbz')
            find_individual_cover(self.folder, 'vol2.cbz')
            find_common_banner(self.folder)

        self.assertEqual(listdir.call_count, 1)

    def test_the_listing_is_read_again_after_the_cache_expires_or_is_cleared(self):
        with patch.object(folder_image.os, 'listdir', wraps=os.listdir) as listdir:
            self.assertIsNone(find_common_cover(self.folder))
            _touch(self.folder, 'cover.jpg')

            self.assertIsNone(find_common_cover(self.folder))  # 캐시가 살아 있으면 새 파일이 아직 안 보인다
            clear_folder_listing_cache()
            self.assertIsNotNone(find_common_cover(self.folder))  # 스캔 시작 시 비우면 바로 보인다

            with patch.object(folder_image.time, 'monotonic', return_value=10 ** 9):
                find_common_cover(self.folder)  # 만료되어 다시 읽는다

        self.assertEqual(listdir.call_count, 3)

    def test_the_cache_stays_bounded(self):
        with patch.object(folder_image, '_LISTING_CACHE_MAX_FOLDERS', 3):
            for index in range(10):
                with tempfile.TemporaryDirectory() as folder:
                    find_common_cover(folder)
            self.assertLessEqual(len(folder_image._listing_cache), 3)


if __name__ == '__main__':
    unittest.main()
