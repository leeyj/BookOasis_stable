# -*- coding: utf-8 -*-
"""
repositories/__init__.py – DB 엔진(DBMS / DB_ENGINE) 환경설정에 따른 동적 리포지토리 노출 라우터
"""
import os
import sys

DBMS = os.getenv("DB_ENGINE", os.getenv("DBMS", "sqlite")).lower()

if DBMS in ("mariadb", "mysql"):
    from repositories.mariadb import (
        annotation_repository,
        audiobook_repository,
        bookmark_repository,
        book_offset_repository,
        book_repository,
        book_scan_repository,
        category_repository,
        collection_repository,
        db_tuning_repository,
        gdrive_book_copy_repository,
        metadata_repository,
        opds_repository,
        plugin_repository,
        reading_progress_repository,
        scanner_queue_repository,
        scheduler_repository,
        series_repository,
        settings_repository,
        trash_repository,
        user_repository,
        video_repository,
    )
else:
    from repositories.sqlite import (
        annotation_repository,
        audiobook_repository,
        bookmark_repository,
        book_offset_repository,
        book_repository,
        book_scan_repository,
        category_repository,
        collection_repository,
        db_tuning_repository,
        gdrive_book_copy_repository,
        metadata_repository,
        opds_repository,
        plugin_repository,
        reading_progress_repository,
        scanner_queue_repository,
        scheduler_repository,
        series_repository,
        settings_repository,
        trash_repository,
        user_repository,
        video_repository,
    )

# 하위 호환성을 위해 sys.modules에 매핑하여 기존 'from repositories.xxx_repository import ...' 임포트 완벽 지원
sys.modules['repositories.annotation_repository'] = annotation_repository
sys.modules['repositories.audiobook_repository'] = audiobook_repository
sys.modules['repositories.bookmark_repository'] = bookmark_repository
sys.modules['repositories.book_offset_repository'] = book_offset_repository
sys.modules['repositories.book_repository'] = book_repository
sys.modules['repositories.book_scan_repository'] = book_scan_repository
sys.modules['repositories.category_repository'] = category_repository
sys.modules['repositories.collection_repository'] = collection_repository
sys.modules['repositories.db_tuning_repository'] = db_tuning_repository
sys.modules['repositories.gdrive_book_copy_repository'] = gdrive_book_copy_repository
sys.modules['repositories.metadata_repository'] = metadata_repository
sys.modules['repositories.opds_repository'] = opds_repository
sys.modules['repositories.plugin_repository'] = plugin_repository
sys.modules['repositories.reading_progress_repository'] = reading_progress_repository
sys.modules['repositories.scanner_queue_repository'] = scanner_queue_repository
sys.modules['repositories.scheduler_repository'] = scheduler_repository
sys.modules['repositories.series_repository'] = series_repository
sys.modules['repositories.settings_repository'] = settings_repository
sys.modules['repositories.trash_repository'] = trash_repository
sys.modules['repositories.user_repository'] = user_repository
sys.modules['repositories.video_repository'] = video_repository

# 직속 임포트 노출 지원 (from repositories import BookRepository)
AnnotationRepository = annotation_repository.AnnotationRepository
AudiobookRepository = audiobook_repository.AudiobookRepository
BookmarkRepository = bookmark_repository.BookmarkRepository
BookOffsetRepository = book_offset_repository.BookOffsetRepository
BookRepository = book_repository.BookRepository
BookScanRepository = book_scan_repository.BookScanRepository
CategoryRepository = category_repository.CategoryRepository
CollectionRepository = collection_repository.CollectionRepository
DbTuningRepository = db_tuning_repository.DbTuningRepository
GdriveBookCopyRepository = gdrive_book_copy_repository.GdriveBookCopyRepository
MetadataRepository = metadata_repository.MetadataRepository
OpdsRepository = opds_repository.OpdsRepository
PluginRepository = plugin_repository.PluginRepository
ReadingProgressRepository = reading_progress_repository.ReadingProgressRepository
ScannerQueueRepository = scanner_queue_repository.ScannerQueueRepository
SchedulerRepository = scheduler_repository.SchedulerRepository
SeriesRepository = series_repository.SeriesRepository
SettingsRepository = settings_repository.SettingsRepository
TrashRepository = trash_repository.TrashRepository
UserRepository = user_repository.UserRepository
VideoRepository = video_repository.VideoRepository
