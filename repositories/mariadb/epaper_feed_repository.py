# -*- coding: utf-8 -*-
"""epaper_feed_repository.py (mariadb) – e-paper 기기 피드 조회. SQL은 repositories/epaper_feed_shared.py."""
from repositories.epaper_feed_shared import make_repository

EpaperFeedRepository = make_repository('%s')
