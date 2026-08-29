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
from api.opds     import opds_bp
from api.app_opds import app_opds_bp
from api.admin    import admin_bp
from api.auth     import auth_bp
from api.dashboard_insights import dashboard_insights_bp
from api.routes.audiobook_routes import audiobook_bp
from api.routes.video_routes import video_bp
from api.routes.collection_routes import collection_bp
from api.routes.annotation_routes import annotation_bp
from api.routes.bookmark_routes import bookmark_bp
from api.routes.plugin_webview_routes import plugin_webview_bp
from api.routes.experimental_routes import experimental_bp

# 통합 Blueprint (URL prefix 없음 – 각 모듈이 전체 경로를 직접 정의)
api_bp = Blueprint('media_api', __name__)

# 하위 Blueprint 등록
api_bp.register_blueprint(stream_bp)
api_bp.register_blueprint(library_bp)
api_bp.register_blueprint(opds_bp)
api_bp.register_blueprint(app_opds_bp)  # 타치요미/미혼 전용 엔드포인트
api_bp.register_blueprint(admin_bp)
api_bp.register_blueprint(auth_bp)
api_bp.register_blueprint(dashboard_insights_bp)
api_bp.register_blueprint(audiobook_bp)
api_bp.register_blueprint(video_bp)
api_bp.register_blueprint(collection_bp)
api_bp.register_blueprint(annotation_bp)
api_bp.register_blueprint(bookmark_bp)
# 관리자 전용이 아니라 로그인 사용자 개인별 기능(화이트리스트 기반)이라 admin_bp가 아닌 여기 직접 등록
api_bp.register_blueprint(plugin_webview_bp)
# 기존 뷰어와 완전 분리된 실험적 기능 테스트용 (프로덕션 뷰어 로직 미사용)
api_bp.register_blueprint(experimental_bp)
