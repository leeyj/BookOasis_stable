# -*- coding: utf-8 -*-
"""
experimental_routes.py - 기존 뷰어 로직과 완전히 분리된 실험적 기능 테스트 라우터.
여기 추가되는 화면들은 프로덕션 뷰어 코드를 전혀 건드리지 않고,
기존 읽기 전용 API(/api/media/stream, /api/media/books/<id>/info)만 재사용한다.
"""
from flask import Blueprint, render_template
from api.auth import login_required

experimental_bp = Blueprint('experimental', __name__)


@experimental_bp.route('/experimental/page-turn', methods=['GET'])
@login_required
def page_turn_test():
    """이미지 기반(zip/cbz) 도서 대상 실제 페이지 넘김 애니메이션 실험 페이지."""
    return render_template('experimental_page_turn.html')
