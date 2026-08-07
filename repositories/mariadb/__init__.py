# -*- coding: utf-8 -*-
"""
repositories/mariadb/__init__.py – MariaDB Native SQL 레포지토리 패키지
"""
from repositories.mariadb import (
    audiobook_repository,
    book_offset_repository,
    book_repository,
    book_scan_repository,
    category_repository,
    collection_repository,
    db_tuning_repository,
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
)

AudiobookRepository = audiobook_repository.AudiobookRepository
BookOffsetRepository = book_offset_repository.BookOffsetRepository
BookRepository = book_repository.BookRepository
BookScanRepository = book_scan_repository.BookScanRepository
CategoryRepository = category_repository.CategoryRepository
CollectionRepository = collection_repository.CollectionRepository
DbTuningRepository = db_tuning_repository.DbTuningRepository
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
