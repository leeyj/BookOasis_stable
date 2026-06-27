# -*- coding: utf-8 -*-
"""
media_server/api.py  ← 하위 호환 래퍼
실제 구현은 media_server/api/ 패키지로 이전되었습니다.

  api/cache.py   – SizedLRUCache, LRUCache, 공용 캐시 인스턴스
  api/stream.py  – /stream, /txt, /pdf, /covers, /cache/stats
  api/library.py – /libraries, /list, /detail, /history
  api/opds.py    – OPDS 전체

NOTE: core.py 에서는 `from api import api_bp` 로 api/ 패키지를 직접 사용합니다.
      이 파일은 참조용으로만 존재합니다.
"""
# 이 파일은 api/ 패키지가 존재하므로 Python이 패키지를 우선 사용합니다.
# 직접 import 시에는 api/__init__.py 가 로드됩니다.
