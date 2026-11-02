# -*- coding: utf-8 -*-
"""남이 만든 이미지(표지·만화 페이지·EPUB 그림)를 Pillow로 열 때 쓰는 단일 입구 (2026-11-02).

Pillow 12.x의 알려진 메모리 버그 대부분은 TIFF·PSD·특수 raw 같은 드문 디코더에 있다. 수정판(13.0)은
Python 3.11 이상 전용이라 3.10 환경(Docker 이미지·네이티브 설치)은 12.x에 남는다. 그래서 확장자와
상관없이 파일 내용으로 판별된 형식이 우리가 쓰는 것(JPEG·PNG·WEBP·GIF·BMP)이 아니면 디코더까지 가지 않고
거부한다. 휴대폰 카메라 JPEG(여러 장 담긴 MPO)는 JPEG 디코더가 함께 처리해 따로 넣지 않는다.
픽셀 수 폭탄은 Pillow 기본 상한(Image.MAX_IMAGE_PIXELS, 약 1.79억 픽셀 초과 시 DecompressionBombError)을 따른다.
"""
from PIL import Image

SAFE_IMAGE_FORMATS = ('JPEG', 'PNG', 'WEBP', 'GIF', 'BMP')


def open_image(fp, mode='r'):
    """Image.open과 같지만 허용한 형식만 연다. 아니면 PIL.UnidentifiedImageError."""
    return Image.open(fp, mode, formats=SAFE_IMAGE_FORMATS)
