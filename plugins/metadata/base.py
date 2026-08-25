# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

class BaseMetadataProvider(ABC):
    """
    모든 도서 메타데이터 제공 플러그인이 구현해야 하는 표준 인터페이스입니다.
    """
    id = "base"
    name = "기본 제공자"
    is_searchable = True
    config_schema = []
    enabled = True
    dashboard_widget = None
    # Optional self-update contract declared by each plugin.
    # Example:
    # {
    #   "enabled": True,
    #   "provider": "github-raw",
    #   "raw_base_url": "https://raw.githubusercontent.com/<org>/<repo>/<branch>/plugins/metadata/<plugin_id>",
    #   "files": ["<plugin_module>.py", "__init__.py", "VERSION"],
    #   "version_file": "VERSION",
    #   "version_key": "plugin version",
    #   "show_sample_update_button": True,
    # }
    update_manifest = None

    def get_db_gateway(self, db_type):
        """Return a cached DB gateway instance for the requested db_type."""
        if not hasattr(self, "_db_gateways"):
            self._db_gateways = {}

        target = db_type or "general"
        if target not in self._db_gateways:
            from services.plugin_db_gateway import PluginDatabaseGateway

            self._db_gateways[target] = PluginDatabaseGateway(target)
        return self._db_gateways[target]

    def get_plugin_config(self, db_type, default=None):
        gateway = self.get_db_gateway(db_type)
        return gateway.get_plugin_config(self.id, default=default)

    def cache_get(self, key):
        """플러그인 전용 Redis 캐시에서 값을 읽는다. 외부 API를 매번 다시
        긁지 않고 결과를 재사용하고 싶을 때 사용한다 (예: 랭킹/검색 결과를
        수 분간 캐시). Redis가 설정되어 있지 않으면 항상 None을 반환한다 —
        호출부는 캐시 미스로 취급해 원본 소스에서 다시 가져오면 된다."""
        from utils.redis_helper import redis_get

        return redis_get(f"plugin:{self.id}:{key}")

    def cache_set(self, key, value, ttl=None):
        """플러그인 전용 Redis 캐시에 값을 저장한다. value는 문자열이어야
        하므로, 구조화된 데이터는 호출부에서 json.dumps()로 직렬화해서
        넘기고 cache_get() 결과를 json.loads()로 복원한다. ttl(초)을 주면
        해당 시간 뒤 자동 만료된다. Redis가 없으면 조용히 False를 반환한다
        (플러그인이 캐시 실패를 치명적 오류로 다룰 필요는 없다)."""
        from utils.redis_helper import redis_set

        return redis_set(f"plugin:{self.id}:{key}", value, ex=ttl)

    def cache_delete(self, key):
        """플러그인 전용 Redis 캐시에서 키를 명시적으로 지운다."""
        from utils.redis_helper import redis_del

        return redis_del(f"plugin:{self.id}:{key}")

    def dispatch_webhook(self, event, payload=None, channels=None):
        """플러그인에서 공용 웹훅 디스패처를 호출하는 편의 헬퍼."""
        from services.webhook_dispatcher import dispatch_webhook_event

        event_name = str(event or '').strip()
        if not event_name:
            event_name = 'event'
        if not event_name.startswith('plugin.'):
            event_name = f"plugin.{self.id}.{event_name}"

        body = dict(payload or {})
        body.setdefault('plugin_id', self.id)
        return dispatch_webhook_event(event_name, body, channels=channels)

    def get_context_menu_items(self, db_type, context):
        """도서 컨텍스트 메뉴 확장 항목 계약 (선택 구현)."""
        return []

    def run_context_menu_action(self, db_type, action_id, context):
        """컨텍스트 메뉴 액션 실행 계약 (선택 구현)."""
        return {'success': False, 'error': 'context menu action not implemented'}

    def get_annotation_context_menu_items(self, db_type, context):
        """EPUB/TXT 뷰어 하이라이트(주석) 우클릭/롱프레스 컨텍스트 메뉴 확장 항목 계약 (선택 구현).
        context에는 annotation_id, book_id, book_title, format, chapter_idx, quote, note, color가 담긴다."""
        return []

    def run_annotation_context_menu_action(self, db_type, action_id, context):
        """하이라이트 컨텍스트 메뉴 액션 실행 계약 (선택 구현)."""
        return {'success': False, 'error': 'annotation context menu action not implemented'}

    def get_dashboard_data(self, db_type, limit=10):
        """대시보드 위젯 데이터 공통 계약 (위젯을 쓰는 플러그인에서 override)."""
        return {'success': False, 'error': 'dashboard widget not implemented'}

    def on_scan_new_books_detected(self, db_type, payload):
        """스캐너 신규도서 감지 후크 (선택 구현)."""
        return {'success': True, 'skipped': True, 'message': 'scan hook not implemented'}

    @abstractmethod
    def search(self, db_type, query):
        """
        주어진 검색어(query)로 도서 후보군 목록을 검색합니다.
        
        Args:
            db_type (str): 데이터베이스 타입 ('prod' 또는 'dev')
            query (str): 검색어 (도서 제목 등)
            
        Returns:
            list[dict]: 검색 결과 목록. 각 dict는 다음 필드를 포함해야 합니다.
                - 'title' (str): 도서 제목
                - 'author' (str): 저자명
                - 'publisher' (str): 출판사명
                - 'pubDate' (str): 출간일
                - 'cover' (str): 표지 이미지 URL
                - 'description' (str): 책 소개/설명
                - 'link' (str): 상세 정보 페이지 URL
        """
        pass

    @abstractmethod
    def apply(self, db_type, book_id, item_data):
        """
        선택된 메타데이터 항목(item_data)을 특정 도서(book_id)에 적용합니다.
        필요 시 표지 이미지를 다운로드하여 저장하고 DB 레코드를 업데이트합니다.
        
        Args:
            db_type (str): 데이터베이스 타입 ('prod' 또는 'dev')
            book_id (int): 변경할 도서의 ID
            item_data (dict): 적용할 도서 메타데이터 정보 (search 결과 중 하나의 아이템)
            
        Returns:
            tuple[bool, str]: (성공 여부, 메시지)
        """
        pass
