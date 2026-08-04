# -*- coding: utf-8 -*-
"""
Pixiv 랭킹 대시보드 위젯 플러그인 (BookOasis metadata plugin)

- search / apply: 검색형 메타데이터 기능은 사용하지 않음 (대시보드 전용)
- dashboard_widget + get_dashboard_data: 픽시브 랭킹 TOP N을 카드로 노출
- 이미지: 로컬 저장 없이, 요청 시점에 서버가 Referer 헤더를 붙여
  픽시브에서 직접 받아온 뒤 base64 데이터 URI로 응답에 포함시켜 프록시.
  (브라우저가 i.pximg.net에 직접 요청하면 Referer 누락으로 403이 나므로
   반드시 서버 사이드에서 중계해야 함)

주의:
- 코어 대시보드 카드 렌더러(공통 데스크 그리드)가 실제로 읽는 필드는
  cover / title / author / publisher / link 입니다.
  (random_gallery 예제 플러그인 소스로 확인됨: https://github.com/yume-script/random_gallery)
  다른 렌더러가 다른 키를 참조할 경우를 대비해 image/image_url/url 등의
  별칭 필드도 함께 채워서 반환합니다.
"""

import base64
import json
import logging
import re
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from plugins.metadata.base import BaseMetadataProvider

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
PIXIV_REFERER = "https://www.pixiv.net/"

# 동시에 받아올 썸네일 최대 개수 (네트워크 부하 제한)
MAX_CONCURRENT_THUMBS = 5
# 개별 요청 타임아웃(초)
REQUEST_TIMEOUT = 8


def _thumb_to_original(thumb_url):
    """
    https://i.pximg.net/c/480x960/img-master/img/2026/08/02/14/53/33/147926455_p0_master1200.jpg
    ==> https://i.pximg.net/img-original/img/2026/08/02/14/53/33/147926455_p0.jpg
    (원본이 png인 작품은 이 변환만으로 404가 날 수 있음 - 참고용으로만 사용)
    """
    if not thumb_url:
        return thumb_url
    original = re.sub(r"/c/\d+x\d+/img-master/", "/img-original/", thumb_url)
    original = original.replace("_master1200", "")
    return original


class PixivRankingMetadataProvider(BaseMetadataProvider):
    id = "pixiv_ranking"
    name = "Pixiv 랭킹"
    is_searchable = False

    config_schema = [
        {
            "key": "PHPSESSID",
            "label": "Pixiv 로그인 세션 (PHPSESSID)",
            "type": "password",
            "required": True,
        },
        {
            "key": "MODE",
            "label": "랭킹 모드",
            "type": "select",
            "default": "daily",
            "options": [
                {"value": "daily", "label": "일간 (daily)"},
                {"value": "weekly", "label": "주간 (weekly)"},
                {"value": "monthly", "label": "월간 (monthly)"},
                {"value": "rookie", "label": "신인 (rookie)"},
                {"value": "original", "label": "오리지널 (original)"},
                {"value": "daily_ai", "label": "AI생성 (daily_ai)"},
                {"value": "male", "label": "남자에게 인기 (male)"},
                {"value": "female", "label": "여자에게 인기 (female)"},
            ],
        },
        {
            "key": "CONTENT",
            "label": "콘텐츠 타입",
            "type": "select",
            "default": "all",
            "options": [
                {"value": "all", "label": "종합 (all)"},
                {"value": "illust", "label": "일러스트 (illust)"},
                {"value": "ugoira", "label": "우고이라 (ugoira)"},
                {"value": "manga", "label": "만화 (manga)"},
            ],
        },
        {
            "key": "LIMIT",
            "label": "표시 개수",
            "type": "select",
            "default": "50",
            "options": [
                {"value": "10", "label": "10개"},
                {"value": "20", "label": "20개"},
                {"value": "30", "label": "30개"},
                {"value": "50", "label": "50개 (최대)"},
            ],
        },
    ]

    # 자동 업데이트를 지원하려면 raw_base_url을 실제 호스팅 리포지토리로 바꿔서 사용
    update_manifest = {
        "enabled": False,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/<org>/<repo>/<branch>/plugins/metadata/pixiv_ranking",
        "files": ["pixiv_ranking.py", "__init__.py", "VERSION"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": False,
    }
    # 대쉬보드에 보여주고 싶을때..
    #dashboard_widget = {
    #    "title": "Pixiv 랭킹",
    #    "subtitle": "픽시브 실시간 랭킹",
    #    "provider": "Pixiv",
    #    "icon": "fa-solid fa-image",
    #    "limit": 10,
    #    "supported_types": ["general"],
    #}

    # 코어 좌측/상단 "카테고리" 내비게이션에 별도 메뉴로 노출되는 풀페이지 탭 계약.
    # (guide_plugins.md에는 없지만 random_gallery 실제 소스로 확인된 계약:
    #  title/icon/order 만 선언하면 되고, 카드 데이터는 get_dashboard_data()를
    #  그대로 재사용함 — 별도 index.html/script.js 불필요)
    category_tab = {
        "title": "Pixiv 랭킹",
        "icon": "fa-solid fa-image",
        "order": 92,
    }

    # ---- 필수 계약 (대시보드 전용이라 실질 동작 없음) ----
    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "대시보드 전용 플러그인입니다."

    # ---- 내부 헬퍼 ----
    def _get_headers(self, session_id, extra=None):
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": PIXIV_REFERER,
        }
        if session_id:
            headers["Cookie"] = f"PHPSESSID={session_id}"
        if extra:
            headers.update(extra)
        return headers

    def _fetch_ranking(self, session_id, mode, content, limit):
        url = (
            f"https://www.pixiv.net/ranking.php"
            f"?mode={mode}&content={content}&format=json"
        )
        logger.warning(
            "[pixiv_ranking] 1/3 랭킹 조회 시작: mode=%s, content=%s, limit=%s, url=%s",
            mode, content, limit, url,
        )
        t0 = time.time()
        req = urllib.request.Request(url, headers=self._get_headers(session_id))
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8")
        elapsed = time.time() - t0
        logger.warning(
            "[pixiv_ranking] 1/3 랭킹 응답 수신: status=%s, %.2fs 소요, body(앞 300자)=%s",
            status, elapsed, raw[:300],
        )
        data = json.loads(raw)
        contents = data.get("contents", [])
        logger.warning(
            "[pixiv_ranking] 1/3 랭킹 파싱 완료: 전체 %d개 중 %d개 사용 예정",
            len(contents), min(limit, len(contents)),
        )
        return contents[:limit]

    def _fetch_thumb_data_uri(self, thumb_url, session_id):
        """썸네일을 다운로드해 base64 data URI로 변환 (로컬 저장 없음)."""
        if not thumb_url:
            logger.warning("[pixiv_ranking] 2/3 썸네일 URL 없음, 건너뜀")
            return None
        t0 = time.time()
        try:
            req = urllib.request.Request(
                thumb_url, headers=self._get_headers(session_id)
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                status = resp.getcode()
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "image/jpeg")
            b64 = base64.b64encode(raw).decode("ascii")
            elapsed = time.time() - t0
            logger.warning(
                "[pixiv_ranking] 2/3 썸네일 수신 성공: status=%s, %.2fs, %d bytes, %s | %s",
                status, elapsed, len(raw), content_type, thumb_url,
            )
            return f"data:{content_type};base64,{b64}"
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            elapsed = time.time() - t0
            logger.warning(
                "[pixiv_ranking] 2/3 썸네일 수신 실패(%.2fs): %s | %s",
                elapsed, e, thumb_url,
            )
            return None

    def _build_items(self, contents, session_id):
        logger.warning(
            "[pixiv_ranking] 2/3 썸네일 %d개 병렬 수집 시작 (동시 %d개)",
            len(contents), MAX_CONCURRENT_THUMBS,
        )
        t0 = time.time()
        items = [None] * len(contents)

        def _work(idx, entry):
            work_id = entry.get("illust_id") or entry.get("id")
            page_url = f"https://www.pixiv.net/artworks/{work_id}"
            thumb_url = entry.get("url")
            image_data_uri = self._fetch_thumb_data_uri(thumb_url, session_id)
            title = entry.get("title")
            rank = entry.get("rank")
            display_title = f"#{rank} {title}" if rank else title
            # 코어 대시보드 카드 렌더러가 실제로 읽는 필드: cover/title/author/publisher/link
            # (random_gallery 플러그인 소스로 확인됨)
            return idx, {
                "cover": image_data_uri,
                "title": display_title,
                "author": entry.get("user_name"),
                "publisher": "Pixiv",
                "link": page_url,
                # 다른 렌더러 대응용 별칭 (혹시 다른 키를 참조하는 경우 대비)
                "image": image_data_uri,
                "image_url": image_data_uri,
                "url": page_url,
                "link_url": page_url,
                "rank": rank,
                # 참고용 원본 이미지 URL 추정치 (png 원본이면 실패할 수 있음)
                "original_url_guess": _thumb_to_original(thumb_url),
            }

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_THUMBS) as pool:
            futures = [
                pool.submit(_work, idx, entry) for idx, entry in enumerate(contents)
            ]
            for fut in as_completed(futures):
                idx, item = fut.result()
                items[idx] = item

        elapsed = time.time() - t0
        success_count = sum(1 for it in items if it.get("cover"))
        logger.warning(
            "[pixiv_ranking] 2/3 썸네일 수집 완료: %.2fs, 성공 %d/%d개",
            elapsed, success_count, len(items),
        )
        return items

    def _get_request_override(self, key):
        """Flask 요청 컨텍스트에서 쿼리 파라미터를 읽음 (프론트엔드 드롭다운 값).
        요청 컨텍스트 밖에서 호출되면(예: 배치 작업) 조용히 None을 반환하고
        설정값(config)으로 폴백함."""
        try:
            from flask import request
            val = request.args.get(key)
            return val if val else None
        except Exception:
            return None

    # ---- 대시보드 계약 ----
    def get_dashboard_data(self, db_type, limit=10):
        logger.warning(
            "[pixiv_ranking] 0/3 get_dashboard_data 호출: db_type=%s, limit=%s",
            db_type, limit,
        )
        cfg = self.get_plugin_config(db_type, default={})
        session_id = cfg.get("PHPSESSID")
        mode = self._get_request_override("mode") or cfg.get("MODE", "daily")
        content = self._get_request_override("content") or cfg.get("CONTENT", "all")

        # 설정에 저장된 "표시 개수"가 있으면, 프론트엔드가 요청한 limit보다
        # 우선 적용한다 (화면 상단/카드 위젯 어느 쪽에서 오든 동일하게 적용).
        try:
            configured_limit = int(cfg.get("LIMIT", 50))
        except (TypeError, ValueError):
            configured_limit = 50
        configured_limit = max(1, min(configured_limit, 50))
        effective_limit = min(limit, configured_limit) if limit else configured_limit

        logger.warning(
            "[pixiv_ranking] 0/3 설정 로드 완료: mode=%s, content=%s, session=%s,"
            " 요청 limit=%s, 설정 표시개수=%s, 최종 limit=%s"
            " (드롭다운으로 요청된 값이 있으면 그 값을 우선 사용)",
            mode, content, "설정됨" if session_id else "없음",
            limit, configured_limit, effective_limit,
        )

        if not session_id:
            logger.warning("[pixiv_ranking] 중단: PHPSESSID 미설정")
            return {
                "success": False,
                "error": "Pixiv 로그인 세션(PHPSESSID)이 설정되지 않았습니다.",
            }

        try:
            contents = self._fetch_ranking(session_id, mode, content, effective_limit)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            logger.warning("[pixiv_ranking] 중단: 랭킹 조회 실패: %s", e)
            return {"success": False, "error": f"랭킹 조회 실패: {e}"}

        if not contents:
            logger.warning("[pixiv_ranking] 랭킹 결과 0건, 빈 목록 반환")
            return {"success": True, "items": []}

        items = self._build_items(contents, session_id)
        logger.warning(
            "[pixiv_ranking] 3/3 완료: 최종 %d개 항목 반환", len(items),
        )
        return {"success": True, "items": items}
