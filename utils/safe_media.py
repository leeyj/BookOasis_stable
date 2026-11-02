# -*- coding: utf-8 -*-
"""책 안에서 꺼낸 리소스를 우리 주소로 내보낼 때의 안전 규칙.

EPUB 안의 파일은 누구나 만들 수 있다. 확장자로 짐작한 형식 그대로 보내면 .html/.xhtml/.svg/.js가
사이트 주소에서 문서로 열려 스크립트가 실행될 수 있다(주소를 직접 열게 유도하면 로그인 세션으로 동작).
그래서 래스터 이미지만 그대로 보내고, SVG는 스크립트가 돌지 못하게 sandbox CSP를 붙이며, 나머지는 거부한다.
"""
from flask import Response, jsonify

RASTER_IMAGE_MIMES = frozenset({
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/avif', 'image/x-ms-bmp',
})

# SVG를 주소로 직접 열어도 스크립트·외부 요청이 막히게(이미지 태그 안에서는 원래 스크립트가 돌지 않는다)
SVG_CSP = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"


def book_resource_response(data, mime, cache_control='public, max-age=31536000'):
    """책 내부 리소스 응답. 허용하지 않는 형식이면 415 JSON을 돌려준다."""
    mime = (mime or '').split(';')[0].strip().lower()
    if mime in RASTER_IMAGE_MIMES:
        res = Response(data, mimetype=mime)
    elif mime == 'image/svg+xml':
        res = Response(data, mimetype=mime)
        res.headers['Content-Security-Policy'] = SVG_CSP
    else:
        return jsonify({'error': 'unsupported resource type'}), 415
    res.headers['Cache-Control'] = cache_control
    res.headers['X-Content-Type-Options'] = 'nosniff'
    return res
