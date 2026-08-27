import logging
from plugins.metadata.base import BaseMetadataProvider

logger = logging.getLogger(__name__)

class BoRelaySsMetadataProvider(BaseMetadataProvider):
    id = "bo_relayss"
    name = "bo.relaySS 중계 서비스"
    description = "GCP 기반 bo.relaySS 중계 서비스와 연동하여 구글 링크 목록을 등록 및 공유하는 플러그인입니다."
    version = "1.0.0"
    author = "BookOasis Team"
    is_searchable = False
    
    # 🌟 최상위 카테고리 메뉴 레벨 등록 선언
    category_tab = {
        "title": "bo.relaySS",
        "icon": "bi-link-45deg",
        "order": 50
    }
    
    # 기본 환경설정 스키마
    config_schema = [
        {
            "name": "user_id",
            "label": "사용자 식별코드",
            "type": "string",
            "default": "",
            "description": "bo.relaySS 서비스 사용자 식별 아이디"
        },
        {
            "name": "domain_url",
            "label": "bo.relaySS 도메인 주소",
            "type": "string",
            "default": "https://bo-relayss.fly.dev",
            "description": "GCP 또는 Fly.io bo.relaySS 서비스의 배포 URL"
        },
        {
            "name": "secret_token",
            "label": "32자리 난수 인증 토큰",
            "type": "string",
            "default": "",
            "description": "자동 생성된 32자리 비밀 토큰"
        }
    ]

    def search(self, title: str, author: str = None, **kwargs):
        """메타데이터 검색 미지원 플러그인"""
        return []

    def apply(self, book_id: int, metadata_id: str, **kwargs):
        """메타데이터 적용 미지원 플러그인"""
        return True
