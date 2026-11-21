# -*- coding: utf-8 -*-
"""그림 변환: 화면(800×480) 안으로 줄이고 디더링해 2색(1비트) PNG로 바꾼다(GRAY_LEVELS가 4단계면 2비트 팔레트). 피드 표지용 JPEG도 만든다."""
import io

from PIL import Image, ImageOps

from services.epaper import profile
from utils.safe_image import open_image  # JPEG·PNG·WEBP·GIF·BMP만 디코더까지 보낸다

_PALETTE_IMAGE = None


def _palette_image():
    global _PALETTE_IMAGE
    if _PALETTE_IMAGE is None:
        pal = Image.new('P', (1, 1))
        flat = []
        for level in profile.GRAY_LEVELS:
            flat += [level, level, level]
        pal.putpalette(flat + [0, 0, 0] * (256 - len(profile.GRAY_LEVELS)))
        _PALETTE_IMAGE = pal
    return _PALETTE_IMAGE


def _open_gray(data, box):
    """bytes → 회색('L') 이미지. 투명 부분은 흰 바탕에 합성, 애니메이션은 첫 장."""
    img = open_image(io.BytesIO(data))
    if img.format == 'JPEG':
        img.draft('L', box)  # 큰 JPEG를 빨리 줄여서 읽는다
    img.seek(0)
    img.load()
    img = ImageOps.exif_transpose(img)
    if img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info):
        img = img.convert('RGBA')
        bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        img = bg
    return img.convert('L')


def _fit_box(size, long_side, short_side):
    w, h = size
    return (long_side, short_side) if w > h else (short_side, long_side)


def _fit(img, long_side, short_side):
    box = _fit_box(img.size, long_side, short_side)
    w, h = img.size
    scale = min(box[0] / w, box[1] / h, 1.0)
    if scale < 1.0:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    return img


def to_epaper_png(data):
    """본문/표지 그림 bytes → (PNG bytes, (가로, 세로)). 못 읽는 형식이면 예외."""
    probe = open_image(io.BytesIO(data))
    box = _fit_box(probe.size, profile.SCREEN_LONG, profile.SCREEN_SHORT)
    img = _fit(_open_gray(data, box), profile.SCREEN_LONG, profile.SCREEN_SHORT)
    if tuple(profile.GRAY_LEVELS) == (0, 255):
        mono = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        out = io.BytesIO()
        mono.save(out, format='PNG', optimize=False)
        return out.getvalue(), mono.size
    quantized = img.convert('RGB').quantize(palette=_palette_image(), dither=Image.Dither.FLOYDSTEINBERG)
    flat = []
    for level in profile.GRAY_LEVELS:
        flat += [level, level, level]
    quantized.putpalette(flat)
    out = io.BytesIO()
    quantized.save(out, format='PNG', optimize=False, bits=2)
    return out.getvalue(), quantized.size


def to_feed_jpeg(data):
    """피드 표지: 그레이스케일 베이스라인 JPEG, 긴 변 FEED_COVER_LONG 이하."""
    long_side = profile.FEED_COVER_LONG
    w, h = open_image(io.BytesIO(data)).size
    scale = min(long_side / max(w, h), 1.0)
    target = (max(1, round(w * scale)), max(1, round(h * scale)))
    img = _open_gray(data, target)
    if img.size != target:
        img = img.resize(target, Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format='JPEG', quality=profile.FEED_COVER_JPEG_QUALITY, progressive=False, optimize=False)
    return out.getvalue()
