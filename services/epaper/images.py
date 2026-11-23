# -*- coding: utf-8 -*-
"""그림 변환: 프로필의 화면 안으로 줄이고 프로필의 그림 형식으로 바꾼다. 피드 표지용 JPEG도 만든다.

- png-dither: 프로필의 회색 단계로 디더링한 PNG(2단계 = 1비트, 4단계 = 2비트, 16단계 = 4비트)
- jpeg / jpeg-color: 회색 / 컬러 베이스라인 JPEG(디더링 없음). 이미 상자 안에 드는 JPEG도 늘 다시 인코딩한다
  (CMYK·EXIF 방향·프로그레시브를 통일하고, 같은 입력이면 같은 바이트).
"""
import io

from PIL import Image, ImageOps

from services.epaper import profile
from utils.safe_image import open_image  # JPEG·PNG·WEBP·GIF·BMP만 디코더까지 보낸다

_PALETTE_IMAGES = {}  # 회색 단계 tuple → 양자화용 팔레트 이미지


def _palette_image(levels):
    pal = _PALETTE_IMAGES.get(levels)
    if pal is None:
        pal = Image.new('P', (1, 1))
        pal.putpalette(_flat_palette(levels) + [0, 0, 0] * (256 - len(levels)))
        _PALETTE_IMAGES[levels] = pal
    return pal


def _flat_palette(levels):
    flat = []
    for level in levels:
        flat += [level, level, level]
    return flat


def _open_gray(data, box):
    """bytes → 회색('L') 이미지. 투명 부분은 흰 바탕에 합성, 애니메이션은 첫 장."""
    return _open(data, box, 'L')


def _open_rgb(data, box):
    """bytes → 'RGB' 이미지. 투명 부분은 흰 바탕에 합성, 애니메이션은 첫 장."""
    return _open(data, box, 'RGB')


def _open(data, box, mode):
    img = open_image(io.BytesIO(data))
    if img.format == 'JPEG':
        img.draft(mode, box)  # 큰 JPEG를 빨리 줄여서 읽는다
    img.seek(0)
    img.load()
    img = ImageOps.exif_transpose(img)
    if img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info):
        img = img.convert('RGBA')
        bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        img = bg
    return img.convert(mode)


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


def to_epaper_png(data, prof=None):
    """본문/표지 그림 bytes → (PNG bytes, (가로, 세로)). 못 읽는 형식이면 예외."""
    prof = prof or profile.DEFAULT_PROFILE
    probe = open_image(io.BytesIO(data))
    box = _fit_box(probe.size, prof.screen_long, prof.screen_short)
    img = _fit(_open_gray(data, box), prof.screen_long, prof.screen_short)
    if prof.png_bits == 1:
        mono = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        out = io.BytesIO()
        mono.save(out, format='PNG', optimize=False)
        return out.getvalue(), mono.size
    levels = prof.gray_levels
    quantized = img.convert('RGB').quantize(palette=_palette_image(levels), dither=Image.Dither.FLOYDSTEINBERG)
    quantized.putpalette(_flat_palette(levels))
    out = io.BytesIO()
    quantized.save(out, format='PNG', optimize=False, bits=prof.png_bits)
    return out.getvalue(), quantized.size


def to_epaper_jpeg(data, prof):
    """본문/표지 그림 bytes → (JPEG bytes, (가로, 세로)). jpeg-color면 컬러, jpeg면 회색('L')."""
    probe = open_image(io.BytesIO(data))
    box = _fit_box(probe.size, prof.screen_long, prof.screen_short)
    src = _open_rgb(data, box) if prof.image_format == 'jpeg-color' else _open_gray(data, box)
    img = _fit(src, prof.screen_long, prof.screen_short)
    out = io.BytesIO()
    img.save(out, format='JPEG', quality=prof.jpeg_quality, progressive=False, optimize=False)
    return out.getvalue(), img.size


def to_epaper_image(data, prof=None):
    """프로필 형식으로 변환 → (bytes, (가로, 세로), 확장자, media-type)."""
    prof = prof or profile.DEFAULT_PROFILE
    if prof.is_jpeg:
        out, size = to_epaper_jpeg(data, prof)
        return out, size, '.jpg', 'image/jpeg'
    out, size = to_epaper_png(data, prof)
    return out, size, '.png', 'image/png'


def to_feed_jpeg(data, prof=None):
    """피드 표지: 그레이스케일 베이스라인 JPEG, 긴 변 프로필의 feed_cover_long 이하."""
    prof = prof or profile.DEFAULT_PROFILE
    long_side = prof.feed_cover_long
    w, h = open_image(io.BytesIO(data)).size
    scale = min(long_side / max(w, h), 1.0)
    target = (max(1, round(w * scale)), max(1, round(h * scale)))
    img = _open_gray(data, target)
    if img.size != target:
        img = img.resize(target, Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format='JPEG', quality=prof.feed_cover_jpeg_quality, progressive=False, optimize=False)
    return out.getvalue()
