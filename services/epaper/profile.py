# -*- coding: utf-8 -*-
"""변환 프로필 v1 수치 (e-paper 리더: 800×480, 본문·그림 1비트).

값을 바꾸면 변환 결과의 바이트가 달라진다 = kosync 문서 id(partial MD5)가 달라진다.
결과가 달라지는 변경은 PROFILE_VERSION을 올려서(v2) 따로 내보낸다. docs/device-api.md에 같은 값이 있다.
"""

PROFILE_VERSION = 'v1'
PROFILE_META_NAME = 'mediaserver:profile'

# 같은 프로필 안에서 변환 결과가 바뀌는 수정(기기 시험 중 조정)을 하면 올린다. 캐시의 변환본이 이 값과 다르면
# 다시 변환한다(새 digest도 같은 책으로 등록된다). 프로필을 공개 고정한 뒤에는 바꾸지 않고 PROFILE_VERSION을 올린다.
CONVERTER_REVISION = 2  # 2: 본문 그림 4단계 그레이 → 2색(1비트)

# 화면: 가로 800 × 세로 480. 그림은 방향에 맞춰 긴 변 800, 짧은 변 480 안에 들어가게 줄인다(키우지 않는다).
SCREEN_LONG = 800
SCREEN_SHORT = 480
# 본문 그림 색 단계. (0, 255) = 2색(1비트 PNG, 기기가 빠른 1비트 갱신을 쓴다), (0, 85, 170, 255) = 4단계 그레이(2비트 PNG)
GRAY_LEVELS = (0, 255)

# 피드 표지 (OPDS 이미지 링크): 그레이스케일 JPEG, 긴 변 이하
FEED_COVER_LONG = 480
FEED_COVER_JPEG_QUALITY = 80

# TXT → EPUB: 챕터를 못 찾았거나 한 챕터가 너무 길면 이 글자 수 안팎에서 문단 경계로 나눈다
TXT_SECTION_CHARS = 20000
TXT_HEADING_MAX_LEN = 50      # 챕터 제목 줄의 최대 길이
TXT_HEADING_MIN_GAP = 300     # 앞 제목과 이 글자 수보다 가까우면 본문 앞 목차로 보고 제목으로 쓰지 않는다

# 신뢰할 수 없는 ZIP을 열 때의 상한 (업로드 + 도서관 파일 공통)
MAX_ZIP_ENTRIES = 10000
MAX_UNCOMPRESSED_TOTAL = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200   # 엔트리별 (압축 해제 크기 / 압축 크기), 1MB 넘는 엔트리에만 적용

# 기기 폰트에 없는 글자가 본문 글자의 이 비율을 넘거나, 종류가 이만큼 넘으면 경고한다
MISSING_GLYPH_RATIO_WARN = 0.001
MISSING_GLYPH_DISTINCT_WARN = 30

# EPUB3 필수 dcterms:modified - 결정적 변환을 위해 원본 값이 없으면 고정 값을 쓴다
FIXED_MODIFIED = '2000-01-01T00:00:00Z'
