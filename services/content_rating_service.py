# -*- coding: utf-8 -*-
"""
content_rating_service.py – 도서 콘텐츠 등급(books_lv) 및 성인 장르/태그 기반 열람 권한 판정

books_lv 컬럼(국내외 등급 표기 혼재: everyone/ma15+/m/r18/adult only/일반/15세/18세,
+ ComicInfo.xml/Kavita YAML 표준 AgeRating 어휘)을 5단계(전체이용가/15세이상/18세이상/성인망가/포르노)로
정규화하고, 관리자가 설정한 "성인 장르/태그 키워드" 목록과 책의 genre/tags 텍스트를
대조해 실질 등급을 산출한다.

ComicInfo.xml AgeRating 원문과 Kavita YAML의 AgeRating 숫자 변환값을 인식하도록 매핑한다.
등급을 모르는 값은 안전을 위해 최고 등급(20)으로 처리해 실제 등급을 낮게 취급하지 않는다.
"""
from services.settings_service import SettingsService

LEVEL_EVERYONE = 0
LEVEL_15 = 15
LEVEL_18 = 18
LEVEL_ADULT_MANGA = 19
LEVEL_PORN = 20

SUPPORTED_CONTENT_RATING_LEVELS = (
    LEVEL_EVERYONE,
    LEVEL_15,
    LEVEL_18,
    LEVEL_ADULT_MANGA,
    LEVEL_PORN,
)

CONTENT_RATING_LABELS = {
    LEVEL_EVERYONE: '전체이용가',
    LEVEL_15: '15세이상',
    LEVEL_18: '18세이상(성인)',
    LEVEL_ADULT_MANGA: '성인망가',
    LEVEL_PORN: '포르노',
}


def get_user_content_rating_max(user):
    """관리자는 항상 최고 등급으로 취급하고, 일반 사용자는 저장된 허용치를 반환한다."""
    if not isinstance(user, dict):
        return LEVEL_18
    if user.get('role') == 'admin':
        return LEVEL_PORN
    try:
        return int(user.get('content_rating_max', LEVEL_18))
    except (TypeError, ValueError):
        return LEVEL_18

_BOOKS_LV_LEVEL_MAP = {
    # 자체 표기 (관리자 편집 UI 드롭다운에서 사용하는 값)
    'everyone': LEVEL_EVERYONE,
    '일반': LEVEL_EVERYONE,
    'ma15+': LEVEL_15,
    'm': LEVEL_18,
    '15세': LEVEL_15,
    'r18': LEVEL_ADULT_MANGA,
    'r18+': LEVEL_ADULT_MANGA,
    '성인망가': LEVEL_ADULT_MANGA,
    'adult manga': LEVEL_ADULT_MANGA,
    'adult only': LEVEL_PORN,
    'adult only 18+': LEVEL_PORN,
    'adultsonly18+': LEVEL_PORN,
    'adults only 18+': LEVEL_PORN,
    '포르노': LEVEL_PORN,
    'porn': LEVEL_PORN,
    'pornography': LEVEL_PORN,
    '18세': LEVEL_18,
    '18세이상': LEVEL_18,
    '18세이상(성인)': LEVEL_18,
    '성인': LEVEL_18,

    # ComicInfo.xml / Kavita YAML 표준 AgeRating 어휘 (대소문자 무시하고 매칭됨)
    'early childhood': LEVEL_EVERYONE,
    'everyone 10+': LEVEL_EVERYONE,
    'g': LEVEL_EVERYONE,
    'kids to adults': LEVEL_EVERYONE,
    'pg': LEVEL_EVERYONE,
    'teen': LEVEL_15,
    'mature 15+': LEVEL_15,
    'mature 17+': LEVEL_18,
    'x18+': LEVEL_PORN,
    # 'unknown'과 'rating pending'은 의도적으로 미포함 - 실제로 등급을 알 수 없다는
    # 뜻이므로, 다른 미인식 값과 마찬가지로 안전 기본값(20)으로 떨어지게 둔다.
}

# 관리자 편집 API에서 허용하는 books_lv 값 (원본 표기 그대로). ComicInfo 파서는 목록에
# 없는 표준 등급도 원문 그대로 저장하므로, 정규화 매핑에서 별도로 처리한다.
ALLOWED_BOOKS_LV_VALUES = (
    'everyone', 'ma15+', 'm', 'r18', 'adult only', 'adult only 18+',
    '일반', '15세', '18세', '성인망가', '포르노',
)


class ContentRatingService:
    @staticmethod
    def normalize_books_lv(books_lv):
        """books_lv 원문 값을 5단계(0/15/18/19/20) 등급으로 정규화.
        비어있으면(NULL) everyone(0), 인식할 수 없는 값은 안전을 위해 최고 등급(20)으로 취급."""
        if not books_lv:
            return LEVEL_EVERYONE
        key = str(books_lv).strip().lower()
        if key in _BOOKS_LV_LEVEL_MAP:
            return _BOOKS_LV_LEVEL_MAP[key]
        return LEVEL_PORN

    @staticmethod
    def get_level_label(level):
        """정규화된 등급 값에 대응하는 사용자 표시 라벨을 반환한다."""
        try:
            normalized_level = int(level)
        except (TypeError, ValueError):
            normalized_level = LEVEL_PORN
        return CONTENT_RATING_LABELS.get(normalized_level, CONTENT_RATING_LABELS[LEVEL_PORN])

    @staticmethod
    def get_adult_keywords():
        """관리자가 설정한 "성인 장르/태그 키워드" 목록 (콤마 구분, 소문자 정규화)"""
        raw = SettingsService.get('ADULT_GENRE_TAG_KEYWORDS', '')
        return [kw.strip().lower() for kw in raw.split(',') if kw.strip()]

    @staticmethod
    def genre_tag_matches_adult(genre, tags, adult_keywords=None):
        # 목록처럼 시리즈 수만큼 반복 호출하는 곳은 get_adult_keywords()를 한 번만 읽어서 넘긴다 -
        # 생략하면 호출마다 설정 테이블을 조회한다.
        keywords = adult_keywords if adult_keywords is not None else ContentRatingService.get_adult_keywords()
        if not keywords:
            return False
        combined = f"{genre or ''} {tags or ''}".lower()
        return any(kw in combined for kw in keywords)

    @staticmethod
    def compute_effective_level(books_lv, genre, tags, adult_keywords=None):
        """books_lv와 성인 장르/태그 키워드 매치 결과 중 더 높은 등급을 최종 등급으로 채택"""
        level = ContentRatingService.normalize_books_lv(books_lv)
        if ContentRatingService.genre_tag_matches_adult(genre, tags, adult_keywords):
            level = max(level, LEVEL_18)
        return level

    @staticmethod
    def can_view_book(db_type, book_id, user_max_level):
        """단일 도서 열람 가능 여부 판정. 도서가 존재하지 않으면 이후 로직(404)에서
        처리하도록 True를 반환한다."""
        try:
            book_id = int(book_id)
        except (TypeError, ValueError):
            return True

        from repositories.book_repository import BookRepository
        row = BookRepository.get_book_rating_info(db_type, book_id)
        if not row:
            return True
        effective_level = ContentRatingService.compute_effective_level(
            row.get('books_lv'), row.get('genre'), row.get('tags')
        )
        try:
            max_level = int(user_max_level)
        except (TypeError, ValueError):
            max_level = LEVEL_PORN
        return max_level >= effective_level
