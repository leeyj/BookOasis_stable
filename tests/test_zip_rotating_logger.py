import os

from utils.logger import ZipRotatingLogger


def _create_archive(log_dir, name, size, mtime):
    archive = log_dir / name
    archive.write_bytes(b'x' * size)
    os.utime(archive, (mtime, mtime))
    return archive


def test_logger_startup_keeps_only_newest_archive_count(tmp_path):
    for index in range(5):
        _create_archive(
            tmp_path,
            f'media_server.log_20260810_12000{index}.zip',
            size=10,
            mtime=index,
        )

    ZipRotatingLogger(
        str(tmp_path / 'media_server.log'),
        max_bytes=100,
        archive_max_files=2,
        archive_max_bytes=1000,
    )

    remaining = sorted(path.name for path in tmp_path.glob('media_server.log_*.zip'))
    assert remaining == [
        'media_server.log_20260810_120003.zip',
        'media_server.log_20260810_120004.zip',
    ]


def test_logger_startup_enforces_archive_total_size(tmp_path):
    for index in range(4):
        _create_archive(
            tmp_path,
            f'lazy_scanner.log_20260810_12000{index}.zip',
            size=40,
            mtime=index,
        )

    ZipRotatingLogger(
        str(tmp_path / 'lazy_scanner.log'),
        max_bytes=100,
        archive_max_files=10,
        archive_max_bytes=90,
    )

    remaining = sorted(tmp_path.glob('lazy_scanner.log_*.zip'))
    assert len(remaining) == 2
    assert sum(path.stat().st_size for path in remaining) == 80


def test_cleanup_does_not_delete_other_log_archives(tmp_path):
    own_archive = _create_archive(
        tmp_path, 'media_server.log_20260810_120000.zip', size=10, mtime=1
    )
    other_archive = _create_archive(
        tmp_path, 'lazy_scanner.log_20260810_120000.zip', size=10, mtime=1
    )

    ZipRotatingLogger(
        str(tmp_path / 'media_server.log'),
        max_bytes=100,
        archive_max_files=0,
        archive_max_bytes=0,
    )

    assert not own_archive.exists()
    assert other_archive.exists()