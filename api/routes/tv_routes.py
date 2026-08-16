# -*- coding: utf-8 -*-
"""
tv_routes.py – 태블릿/TV 거치용 킷오스크 뷰어 화면 라우터
설정/관리 메뉴가 없는 콘텐츠 전용 UI(/tv)와, 그 화면에서 책을 탭했을 때
사이드바 없이 리더만 바로 여는 킷오스크 모드(/?kiosk=1)를 제공한다.
"""
from flask import Blueprint, render_template, session

tv_bp = Blueprint('tv', __name__)


@tv_bp.route('/tv', methods=['GET'])
def tv_index():
    """
    설정/관리 메뉴 없이 카테고리 드로어 + 커버 그리드만 있는 독립 UI.
    페이지 셸 자체는 로그인 여부와 무관하게 렌더링하고(민감 데이터 없음),
    실제 데이터 API는 각자 @login_required로 보호되어 있어 로그아웃 상태면
    401을 받고 tv.js가 화면 안에서 팝업 로그인 폼을 띄운다(킷오스크 UX 유지 목적).
    """
    return render_template(
        'tv.html',
        tv_username=session.get('username'),
        tv_role=session.get('role')
    )
