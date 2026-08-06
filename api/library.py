# -*- coding: utf-8 -*-
"""
api/library.py - 라이브러리/도서/플러그인 통합 블루프린트 모듈
도메인별로 분리된 하위 블루프린트(media_library_routes, book_routes, plugin_routes)를 결합합니다.
"""
from flask import Blueprint

from api.routes.media_library_routes import media_library_routes_bp
from api.routes.book_routes import book_routes_bp
from api.routes.plugin_routes import plugin_routes_bp

# 하위 호환성을 유지하는 통합 Blueprint
library_bp = Blueprint('media_library', __name__)

library_bp.register_blueprint(media_library_routes_bp)
library_bp.register_blueprint(book_routes_bp)
library_bp.register_blueprint(plugin_routes_bp)
