# -*- coding: utf-8 -*-
"""기기 모델 → 변환 프로필 표 (기여자가 한 줄씩 더하는 곳. 안내: docs/epaper-devices.md).

사용자 설정(EPAPER_WEB_DEVICE / EPAPER_FEED_DEVICE)에는 모델 id가 저장된다.
- 모델 id는 한번 정하면 바꾸지 않는다(바꾸면 저장된 설정이 끊긴다). 소문자·숫자·'-'만, 'local-' 접두사 금지.
- 이름(name, name_en)은 화면 표시용이라 언제든 고쳐도 된다.
- use: 'web' = 웹 메뉴 "기기용 받기"에만, 'feed' = 기기 피드(/opds-epaper)에만, 'both' = 둘 다.
- 프로필 고르는 기준: 컬러 화면 → color-hd / Kindle 항목은 예외(web 전용, color-hd) /
  나머지는 화면 짧은 변이 758 이하 → gray-low, 넘으면 gray-hd. 저사양 1비트 기기는 해상도별 프로필.
- 사양 출처(짧은 변 픽셀 수, 컬러 여부)가 없는 기기는 넣지 않는다. 모델을 다른 프로필로 옮기면
  그 모델 사용자의 변환본·digest가 바뀌므로 프로필 값 수정과 같은 무게로 검토한다.
"""
from collections import namedtuple

USES = ('web', 'feed', 'both')

DeviceModel = namedtuple('DeviceModel', 'id name name_en profile use verified source')

MODELS = (
    DeviceModel('seeed-reterminal', 'Seeed reTerminal (e-paper)', 'Seeed reTerminal (e-paper)', 'v1', 'both', True,
                'device test 2026-11'),
    DeviceModel('xteink-x4', 'Xteink X4 (X4 Pro, X4 Classic)', 'Xteink X4 (X4 Pro, X4 Classic)', 'x4', 'both', False,
                'https://github.com/Free-Ink/freeink-sdk (800x480, B/W + 4-level gray)'),
    DeviceModel('xteink-x3', 'Xteink X3', 'Xteink X3', 'x3', 'both', False,
                'https://github.com/Free-Ink/freeink-sdk (792x528, B/W + 4-level gray)'),
    DeviceModel('kobo-758', 'Kobo Nia', 'Kobo Nia', 'gray-low', 'both', False,
                'https://ereader.kobo.com/en-us/products/kobo-nia (1024x758)'),
    DeviceModel('kobo-1072', 'Kobo Clara HD / Clara 2E / Clara BW', 'Kobo Clara HD / Clara 2E / Clara BW', 'gray-hd', 'both', False,
                'https://en.wikipedia.org/wiki/Kobo_eReader, https://ereader.kobo.com/en-ww/products/kobo-clara-bw (1072x1448)'),
    DeviceModel('kobo-1264', 'Kobo Libra H2O / Libra 2', 'Kobo Libra H2O / Libra 2', 'gray-hd', 'both', False,
                'https://en.wikipedia.org/wiki/Kobo_eReader (1264x1680)'),
    DeviceModel('kobo-1404', 'Kobo Aura ONE / Elipsa / Elipsa 2E', 'Kobo Aura ONE / Elipsa / Elipsa 2E', 'gray-hd', 'both', False,
                'https://en.wikipedia.org/wiki/Kobo_eReader (1404x1872)'),
    DeviceModel('kobo-1440', 'Kobo Sage / Forma', 'Kobo Sage / Forma', 'gray-hd', 'both', False,
                'https://en.wikipedia.org/wiki/Kobo_eReader (1440x1920)'),
    DeviceModel('kobo-color', 'Kobo Libra Colour / Clara Colour', 'Kobo Libra Colour / Clara Colour', 'color-hd', 'both', False,
                'https://ereader.kobo.com/en-us/products/kobo-libra-colour, https://en.wikipedia.org/wiki/Kobo_eReader (color)'),
    DeviceModel('kindle-send', 'Kindle (Send to Kindle용)', 'Kindle (for Send to Kindle)', 'color-hd', 'web', False,
                'stock Kindle reads EPUB only through Send to Kindle (Amazon re-converts)'),
    # 예시 기기: 커뮤니티 정리 표(2026-11). 컬러 화면 기기도 컬러가 필요 없으면 여기를 고른다.
    DeviceModel('generic-hd', '기타 기기: 고해상도 (짧은 변 758px 초과, 크레마·리디페이퍼·Boox·교보 sam 등)',
                'Other device: high resolution (short side > 758px, e.g. Crema, RIDIPAPER, Boox, Kyobo sam)',
                'gray-hd', 'both', False, 'generic'),
    DeviceModel('generic-low', '기타 기기: 저해상도 (짧은 변 758px 이하, 루나·Boox Poke 5S 등)',
                'Other device: low resolution (short side <= 758px, e.g. Luna, Boox Poke 5S)',
                'gray-low', 'both', False, 'generic'),
)

_BY_ID = {m.id: m for m in MODELS}


def get_model(model_id):
    return _BY_ID.get(str(model_id or '').strip())


def models_for(kind):
    """kind: 'web' | 'feed' → 그 설정에 고를 수 있는 모델 목록."""
    return [m for m in MODELS if m.use in (kind, 'both')]


def usable_for(model, kind):
    return model is not None and model.use in (kind, 'both')
