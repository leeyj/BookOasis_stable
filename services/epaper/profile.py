# -*- coding: utf-8 -*-
"""변환 프로필: 화면 등급마다 다른 수치(화면, 그림 형식, 표지)를 담는 객체와, 기기와 상관없는 변환기 공통 상한.

프로필은 기기 모델이 아니라 화면 등급이다. 모델 → 프로필 연결은 devices.py 의 모델 표가 맡는다.
프로필 값을 바꾸면 변환 결과의 바이트가 달라진다 = kosync 문서 id(partial MD5)가 달라진다.
값을 고치면 그 프로필의 revision을 올린다(id는 그대로). 새 id는 화면 등급 자체가 새로 필요할 때만 만든다
(새 저사양 해상도, 컬러 등). id는 OPF 표식·X-Epaper-Profile 헤더·캐시 키로 공개되므로 한번 정하면 바꾸지 않는다.
docs/device-api.md 에 같은 표가 있다.
"""
import re
from dataclasses import dataclass

PROFILE_META_NAME = 'mediaserver:profile'

IMAGE_FORMATS = ('png-dither', 'jpeg', 'jpeg-color')
_PNG_BITS = {2: 1, 4: 2, 16: 4}  # 회색 단계 수 → PNG 팔레트 비트
ID_PATTERN = re.compile(r'^[a-z0-9-]+$')  # 점은 캐시 키 구분자라 금지. 공식 id에는 'local-' 접두사를 쓰지 않는다(예약)


@dataclass(frozen=True)
class Profile:
    """화면 등급 프로필. id는 OPF 표식, 캐시 키, X-Epaper-Profile 헤더에 그대로 쓰인다."""
    id: str
    # 화면. 그림은 방향에 맞춰 긴 변 screen_long, 짧은 변 screen_short 안에 들어가게 줄인다(키우지 않는다).
    screen_long: int
    screen_short: int
    # 본문 그림 형식: 'png-dither' = gray_levels 단계로 Floyd–Steinberg 디더링한 PNG,
    # 'jpeg' = 회색 JPEG(디더링 없음), 'jpeg-color' = 컬러 JPEG.
    image_format: str = 'png-dither'
    # png-dither 전용. (0, 255) = 2색(1비트 PNG), 4단계 = 2비트 PNG, 16단계 = 4비트 PNG. JPEG 형식은 ()
    gray_levels: tuple = ()
    jpeg_quality: int = 80
    # 피드 표지 (OPDS 이미지 링크): 그레이스케일 JPEG, 긴 변 이하
    feed_cover_long: int = 480
    feed_cover_jpeg_quality: int = 80
    # 이 프로필의 값을 고치면 올린다. 캐시 메타에 값이 없으면 1로 본다(3.2.0 캐시 호환)
    revision: int = 1
    # 실기기로 확인했는가 (표시용, 동작에 영향 없음)
    device_verified: bool = False
    # BookOasis 펌웨어 기기(기기 cpfont로 그린다): 글자 경고를 기기 폰트 범위(text.device_fonts)로 내고,
    # 펌웨어가 잘못 그리는 RLM류·IVS를 본문에서 지운다(text.strip_invisible). 다른 기기는 자기 폰트·렌더러를 쓰므로 False
    bookoasis_firmware: bool = False

    def __post_init__(self):
        levels = tuple(self.gray_levels)
        object.__setattr__(self, 'gray_levels', levels)
        if not ID_PATTERN.match(self.id or ''):
            raise ValueError(f'profile {self.id!r}: id must be lowercase letters, digits and "-"')
        if not (0 < self.screen_short <= self.screen_long):
            raise ValueError(f'profile {self.id}: bad screen size')
        if self.image_format not in IMAGE_FORMATS:
            raise ValueError(f'profile {self.id}: image_format must be one of {IMAGE_FORMATS}')
        if self.image_format == 'png-dither':
            if len(levels) not in _PNG_BITS or levels[0] != 0 or levels[-1] != 255 or list(levels) != sorted(set(levels)):
                raise ValueError(f'profile {self.id}: gray_levels must be 2, 4 or 16 ascending values from 0 to 255')
        elif levels:
            raise ValueError(f'profile {self.id}: gray_levels is only for png-dither')
        if not (1 <= self.jpeg_quality <= 95) or not (1 <= self.feed_cover_jpeg_quality <= 95):
            raise ValueError(f'profile {self.id}: jpeg quality must be 1..95')
        if int(self.revision) < 1:
            raise ValueError(f'profile {self.id}: revision starts at 1')

    @property
    def png_bits(self):
        return _PNG_BITS[len(self.gray_levels)]

    @property
    def is_jpeg(self):
        return self.image_format != 'png-dither'


# Seeed reTerminal (800×480, ESP32-S3). 실기기 확인됨. 그림은 속도를 위해 2색(1비트).
RETERMINAL_V1 = Profile(id='v1', screen_long=800, screen_short=480, gray_levels=(0, 255), device_verified=True,
                        bookoasis_firmware=True)

# Xteink X4 (800×480). 처음 값은 v1과 같지만 v1(reTerminal 실기기 시험)과 따로 조정하려고 나눈다.
# 4단계 회색을 지원하지만 저사양이라 속도를 위해 2색으로 보낸다.
XTEINK_X4 = Profile(id='x4', screen_long=800, screen_short=480, gray_levels=(0, 255), bookoasis_firmware=True)

# Xteink X3 (792×528). 2색인 이유는 X4와 같다.
XTEINK_X3 = Profile(id='x3', screen_long=792, screen_short=528, gray_levels=(0, 255), bookoasis_firmware=True)

# 고해상도 기기는 그림 크기를 기기가 맞추고 회색을 직접 표현하므로 등급 몇 개로 묶는다.
# 화면 짧은 변이 758 이하 → gray-low, 넘으면 gray-hd, 컬러 화면 → color-hd.
GRAY_LOW = Profile(id='gray-low', screen_long=1024, screen_short=758, image_format='jpeg')
GRAY_HD = Profile(id='gray-hd', screen_long=1680, screen_short=1264, image_format='jpeg')
COLOR_HD = Profile(id='color-hd', screen_long=1680, screen_short=1264, image_format='jpeg-color')

PROFILES = {p.id: p for p in (RETERMINAL_V1, XTEINK_X4, XTEINK_X3, GRAY_LOW, GRAY_HD, COLOR_HD)}
DEFAULT_PROFILE = RETERMINAL_V1

# 모든 프로필의 변환 결과가 바뀌는 수정(정규화 등)을 하면 올린다. 캐시의 변환본이 이 값과 다르면
# 다시 변환한다(새 digest도 같은 책으로 등록된다). 한 프로필의 값만 바꿀 때는 그 프로필의 revision을 올린다.
# 3은 펌웨어 프로필 EPUB과 TXT(프로필 공통)에서 RLM류·IVS를 지우는 수정이다. TXT 때문에 전역 값을 올렸고,
# 프로필 revision은 표지 캐시 이름에도 들어가므로 올리지 않았다. 그 문자가 없는 책은 다시 변환해도 바이트가 같다(digest 유지).
CONVERTER_REVISION = 3  # 2: 본문 그림 4단계 그레이 → 2색(1비트), 3: RLM류·IVS 삭제

# ---- 기기와 상관없는 공통 값 ----

# TXT → EPUB 변환은 프로필과 무관하다: 늘 이 조각 길이와 표식 TXT_PROFILE_ID 로 만든다.
# (partial MD5는 파일 앞쪽만 읽어, 조각 길이가 다르면 digest는 같은데 spine이 달라질 수 있다)
TXT_PROFILE_ID = 'v1'
TXT_SECTION_CHARS = 20000     # 챕터를 못 찾았거나 한 챕터가 너무 길면 이 글자 수 안팎에서 문단 경계로 나눈다
TXT_HEADING_MAX_LEN = 50      # 챕터 제목 줄의 최대 길이
TXT_HEADING_MIN_GAP = 300     # 앞 제목과 이 글자 수보다 가까우면 본문 앞 목차로 보고 제목으로 쓰지 않는다

# 신뢰할 수 없는 ZIP을 열 때의 상한 (업로드 + 도서관 파일 공통)
MAX_ZIP_ENTRIES = 10000
MAX_UNCOMPRESSED_TOTAL = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200   # 엔트리별 (압축 해제 크기 / 압축 크기), 1MB 넘는 엔트리에만 적용

# 기기 폰트에 없는 글자가 본문 글자의 이 비율을 넘거나, 종류가 이만큼 넘으면 경고한다 (펌웨어 기본 폰트 기준)
MISSING_GLYPH_RATIO_WARN = 0.001
MISSING_GLYPH_DISTINCT_WARN = 30

# EPUB3 필수 dcterms:modified - 결정적 변환을 위해 원본 값이 없으면 고정 값을 쓴다
FIXED_MODIFIED = '2000-01-01T00:00:00Z'
