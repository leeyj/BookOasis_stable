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
    # 사용자가 설정에서 "홈 화면 플러그인 배치 모드"를 켰을 때만 실제 홈 대시보드에 노출되는
    # 위젯 선언 (선택). dashboard_widget([플러그인] 공통 데스크 탭용)과는 별개 계약이다 —
    # 이름이 비슷해 혼동하기 쉬우니 주의. 데이터 조회는 get_dashboard_data()를 그대로 재사용한다.
    # Example:
    # home_widget = {
    #     'title': '오늘의 추천곡',
    #     'subtitle': 'Karaoke Plugin',
    #     'icon': 'fa-solid fa-music',
    #     'order': 60,
    #     'limit': 10,
    #     'sessions': 'all',  # _resolve_plugin_sessions()와 동일 규칙 (all / 리스트 / 미지정→general)
    #     'layout': 'grid',  # 'full'(기본, 1열 전체 차지) | 'grid'(카드처럼 다른 grid 위젯과 한 행에 나란히 배치)
    #     'size': 2,  # 'grid'일 때만 의미 있음. 1(기본)/2/3 - auto-fill 컬럼 기준 몇 칸을 이어 붙일지
    # }
    # 커스텀 CSS/이미지가 필요하면 플러그인 디렉토리에 dashboard.html/dashboard.css(선택:
    # dashboard.js)를 두면 된다(category_tab의 index.html/style.css/script.js와 동일한
    # 서빙 방식 - MetadataFactory._load_plugin_ui_bundle(..., target='dashboard')). 프론트가
    # 위젯마다 Shadow DOM을 만들어 그 안에서만 렌더링하므로 다른 위젯이나 앱 전역 CSS와
    # 서로 오염되지 않는다. 단, get_dashboard_data()가 반환한 값을 dashboard.html/js 안에
    # 끼워 넣을 때 이스케이프는 플러그인 책임이다(category_tab 뷰와 동일한 신뢰 모델).
    # 이 파일들이 없으면 기존처럼 get_dashboard_data()의 items를 안전한 화이트리스트
    # 렌더러로만 표시한다(하위 호환, 마이그레이션 불필요).
    home_widget = None
    # 도서 상세 페이지 사이드바에 위젯을 마운트하려면 선언 (선택).
    # Example:
    # detail_sidebar_widget = {"title": "이 작가의 다른 도서", "order": 50, "sessions": "all"}
    detail_sidebar_widget = None
    # "스마트 추천" 화면(최근 읽은 시리즈 기준 추천, tab_smart_recommend.js)에 코어 기본 제공
    # 장르/태그/작가 섹션과 나란히 플러그인 전용 섹션을 추가하려면 선언 (선택).
    # detail_sidebar_widget과 동일한 사고방식이지만 화면이 다르다 - 상세페이지 사이드바가
    # 아니라 스마트 추천 탭에 노출된다. get_smart_recommend_data(db_type, context)를 구현해야
    # 한다 (get_detail_sidebar_data와 동일한 items 스키마 공유 - metric/link/book_id 카드).
    # Example:
    # smart_recommend_widget = {"title": "공식 연관작", "order": 10, "sessions": "all"}
    smart_recommend_widget = None
    # 도서 상세 페이지 본문(표지/제목/시놉시스/볼륨 목록) 전체를 이 플러그인의 커스텀 화면으로
    # 대체할 수 있다고 선언 (선택). detail_sidebar_widget과 달리 여러 플러그인이 동시에 활성화될
    # 수 없는 "단일 슬롯 교체" 계약 — 세션(session)별로 관리자가 설정 화면에서 활성 플러그인을
    # 하나만 선택한다(기본값은 항상 코어 내장 화면). 플러그인 디렉토리의 detail/index.html,
    # detail/style.css, detail/script.js 번들이 category_tab과 동일한 방식으로 서빙된다.
    # Example:
    # detail_view = {"title": "AniList 스타일 상세", "sessions": "all"}
    detail_view = None
    # 도서 상세 페이지 헤더의 정적 점수 별(.detail-score, 검색 메타데이터에서 온 읽기 전용
    # 외부 평점)을 클릭 가능한 커뮤니티 별점으로 대체하려면 선언 (선택). detail_sidebar_widget과
    # 달리 여러 플러그인이 동시에 활성화될 수 없는 "단일 슬롯 교체" 계약이다 — 활성화된
    # provider가 여럿이면 order가 가장 작은 것 하나만 쓰인다. sessions에 'general'만 두면
    # (성인/오디오북/영상 강좌에 노출하면 안 되는 기능이라) _resolve_plugin_sessions()가
    # 자동으로 그 외 세션에서 배제해준다. get_rating_widget_data(db_type, context)와
    # submit_rating(db_type, context, rating)을 구현해야 한다.
    # Example:
    # rating_widget = {"title": "커뮤니티 별점", "order": 10, "sessions": "general"}
    rating_widget = None
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

    def report_problem(self, code, *, title, detail='', severity='notice', db_type='general',
                       target_type='system', target_id=None, action_id=None, action_label=None,
                       message=None, library_id=None, series_name=None, target_path=None):
        """관리자 알림센터에 문제 카드를 올린다 (선택 계약, BookOasis 2.8.4+).

        같은 (code, target)으로 다시 부르면 새 줄이 생기지 않고 횟수/마지막 시각만 늘어난다.
        다음에 성공하면 resolve_problem()으로 해결 처리한다 - 열린 행이 0이 되면 카드가 사라진다.

        Args:
            code (str): 플러그인 안에서만 유일하면 된다 (영문/숫자/_ . -, 64자 이내).
                        코어가 '<plugin id>:<code>'로 저장해 다른 플러그인과 겹치지 않는다.
            title (str): 카드 제목 (플러그인이 직접 제공하는 문구, 300자 이내). 카드에는 플러그인 이름이 앞에 붙는다.
            detail (str): 설명/해결 방법 한 줄 (선택).
            severity (str): 'notice'(참고, 기본) 또는 'action_required'(조치 필요 - 관리자 아이콘에 빨간 점).
            db_type (str): 'general'/'adult'/'audiobook'/'video'.
            target_type (str): 'system'(기본, 도서와 무관) / 'book' / 'series' / 'library'.
            target_id: book_id, library_id 등. 'system'이면 생략.
                       'book'이면 코어가 시리즈/카테고리/경로를 채워 카드 안에서 시리즈별로 묶고 [진단]을 붙인다.
            action_id (str): 카드/줄의 조치 버튼. 누르면 이 플러그인의
                             run_context_menu_action(db_type, action_id, context)가 불린다 (기존 액션 RPC).
                             context = {source: 'problem_card', group_key, problem_code, target_type?, target_id?, book_id?}
            action_label (str): 버튼 문구 (없으면 '실행').
            message (str): 원문 오류(선택, 접어서 보관).

        Returns:
            bool: 기록 성공 여부. 잘못된 인자나 저장 실패여도 예외를 내지 않는다.

        플러그인별 열린 문제는 최대 1,000건이며 넘으면 오래된 것부터 해결 처리된다. 플러그인을 끄면 열린 문제는
        해결 처리된다. 관리자에게만 보인다. 구버전 코어와 함께 쓰려면 hasattr(self, 'report_problem')로 확인한다.
        """
        from services.plugin_problem_service import report

        return report(self.id, code, title=title, detail=detail, severity=severity, db_type=db_type,
                      target_type=target_type, target_id=target_id, action_id=action_id,
                      action_label=action_label, message=message, library_id=library_id,
                      series_name=series_name, target_path=target_path, plugin_name=getattr(self, 'name', None))

    def resolve_problem(self, code, *, db_type='general', target_type='system', target_id=None):
        """report_problem()으로 올린 문제를 해결 처리한다 (선택 계약, BookOasis 2.8.4+).
        열린 문제가 없으면 아무것도 하지 않고 False를 돌려준다 - 성공할 때마다 불러도 된다."""
        from services.plugin_problem_service import resolve

        return resolve(self.id, code, db_type=db_type, target_type=target_type, target_id=target_id)

    def lookup_music_album(self, db_type, context):
        """음악 앨범 정보 조회 계약 (선택 구현, BookOasis 2.8.4+).

        오디오북 세션의 '음악' 속성 카테고리에서 album.yaml이 없는 앨범을 코어가 스캔 뒤 백그라운드로
        천천히(앨범 사이 5초) 물어본다. 앨범마다 한 번만 묻고, 결과(못 찾음 포함)를 기억해 다시 묻지 않는다.
        돌려준 값은 앨범의 빈 칸(아티스트/발매 연도/소개/커버)에만 보이고, 스캔 결과를 덮어쓰지 않는다.

        Args:
            db_type (str): 'audiobook'
            context (dict): {
                'folder_name': 앨범 폴더 이름 (예: '[2008.01.17 정규앨범] Andy The First New Dream'),
                'artist': 곡 태그로 정한 앨범 아티스트 (없으면 ''),
                'track_titles': 앞쪽 곡 제목 몇 개 (list[str]),
                'track_count': 곡 수,
            }

        Returns:
            dict | None: 찾으면 {'artist', 'year', 'genres'(list[str]), 'summary', 'cover_url', 'source_url'} 중
            아는 것만. 못 찾으면 None. 예외를 내면 이번엔 건너뛰고 다음 주기에 다시 묻는다.
        """
        return None

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

    def get_detail_sidebar_data(self, db_type, context):
        """도서 상세 페이지 사이드바 위젯 데이터 계약 (detail_sidebar_widget을 쓰는 플러그인에서 override).

        Args:
            db_type (str): 'general'/'adult'/'audiobook'/'video'
            context (dict): series_name, library_id, book_id, author, genre, tags

        Returns:
            dict: {'success': True, 'title': str(선택, 미지정 시 manifest title 사용),
                   'items': list[dict]} - items는 대시보드 위젯과 동일한 아이템 스키마
                   (book_id/series_name으로 내부 도서 연결, 'link'로 외부 URL 연결,
                   item_type='metric'으로 도서와 무관한 자유 형식 카드 표시).
        """
        return {'success': False, 'error': 'detail sidebar widget not implemented'}

    def get_rating_widget_data(self, db_type, context):
        """도서 상세 페이지 헤더 별점 위젯 데이터 계약 (rating_widget을 쓰는 플러그인에서 override).

        Args:
            db_type (str): 'general' (성인/오디오북/영상 강좌는 이 계약 자체가 노출되지 않는다)
            context (dict): series_name, library_id, book_id, author, isbn

        Returns:
            dict: {'success': True, 'average': float, 'count': int, 'my_rating': int|None}
        """
        return {'success': False, 'error': 'rating widget not implemented'}

    def submit_rating(self, db_type, context, rating):
        """도서 상세 페이지 헤더 별점 제출 계약 (rating_widget을 쓰는 플러그인에서 override).

        Args:
            db_type (str): 'general'
            context (dict): get_rating_widget_data와 동일
            rating (int): 1~5

        Returns:
            dict: {'success': True, 'average': float, 'count': int, 'my_rating': int} 또는
                  {'success': False, 'error': str}
        """
        return {'success': False, 'error': 'rating widget not implemented'}

    def on_scan_new_books_detected(self, db_type, payload):
        """스캐너 신규도서 감지 후크 (선택 구현)."""
        return {'success': True, 'skipped': True, 'message': 'scan hook not implemented'}

    def start_background_service(self, db_type):
        """플러그인 상시 백그라운드 서비스 시작 후크 (선택 구현).
        앱 부팅 시 활성화된 플러그인에 한해 1회 호출된다. 오래 걸리는 초기화나
        블로킹 루프는 반드시 자체 스레드로 넘기고 이 메서드는 즉시 반환해야 한다."""
        return None

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
