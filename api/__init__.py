# -*- coding: utf-8 -*-
"""
api/__init__.py
모든 하위 Blueprint를 하나의 api_bp로 통합하여 외부에 노출합니다.

사용법 (core.py):
    from api import api_bp
    app.register_blueprint(api_bp)
"""
from flask import Blueprint

from api.stream  import stream_bp
from api.library import library_bp
from api.opds    import opds_bp
from api.admin   import admin_bp
from api.auth    import auth_bp

# 통합 Blueprint (URL prefix 없음 – 각 모듈이 전체 경로를 직접 정의)
api_bp = Blueprint('media_api', __name__)

# 하위 Blueprint 등록
api_bp.register_blueprint(stream_bp)
api_bp.register_blueprint(library_bp)
api_bp.register_blueprint(opds_bp)
api_bp.register_blueprint(admin_bp)
api_bp.register_blueprint(auth_bp)
