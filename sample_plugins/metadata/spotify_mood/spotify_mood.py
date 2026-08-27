# -*- coding: utf-8 -*-
"""
spotify_mood.py -- 지금 이 무드에 어울리는 Spotify 플레이리스트/트랙을 추천하고,
검색까지 할 수 있는 기분전환용 샘플 플러그인.

- 인증: Client Credentials Flow (Spotify 계정 로그인 불필요, 검색/조회 전용 API만
  사용하므로 CLIENT_ID/CLIENT_SECRET 두 값만 있으면 됨). 발급받은 액세스 토큰은
  self.cache_set()으로 Redis에 캐싱해서 매 요청마다 재발급받지 않는다.
- dashboard_widget: 공통 데스크에 "지금 이 무드" 카드로 시간대별 추천 플레이리스트를 노출.
- category_tab: 사이드바 1등 시민 탭에서 무드 수동 선택 + 자유 검색(플레이리스트/트랙/
  아티스트/앨범) 풀페이지 UI 제공. pixiv_ranking 샘플과 동일하게 dashboard_widget의
  get_dashboard_data() 엔드포인트를 재사용하고, flask.request.args로 추가 파라미터
  (mood/q/kind)를 받는다.
- OAuth (선택, "내 플레이리스트"용): Authorization Code Flow. 서버(운영자) 전체가 계정 1개를
  공유하는 구조 - 코어의 범용 콜백 브릿지(GET /callback, api/routes/plugin_routes.py)가
  state에 담긴 plugin_id를 보고 이 플러그인의 handle_oauth_callback()에 위임해준다.
  발급받은 refresh_token은 이 플러그인의 config(REFRESH_TOKEN 필드)에 영속 저장한다.
"""
import json
import logging

import requests

from plugins.metadata.base import BaseMetadataProvider

logger = logging.getLogger(__name__)

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_OAUTH_SCOPES = "playlist-read-private playlist-read-collaborative"
REQUEST_TIMEOUT = 8

# 시간대별 기본 무드 정의. hours는 datetime.now().hour 기준 범위(끝값 미포함).
MOOD_DEFS = [
    {"key": "dawn", "label": "🌙 새벽 감성", "hours": range(0, 5), "query": "late night lofi sleep chill"},
    {"key": "morning", "label": "☀️ 아침 활력", "hours": range(5, 8), "query": "morning motivation upbeat"},
    {"key": "focus", "label": "🎯 집중 모드", "hours": range(8, 12), "query": "deep focus instrumental study"},
    {"key": "lunch", "label": "🍚 점심 브레이크", "hours": range(12, 14), "query": "feel good pop lunch"},
    {"key": "afternoon", "label": "☕ 오후 나른함", "hours": range(14, 18), "query": "afternoon acoustic chill coffee"},
    {"key": "evening", "label": "🌆 저녁 무드", "hours": range(18, 21), "query": "evening chill relax"},
    {"key": "night", "label": "🌃 밤 분위기", "hours": range(21, 24), "query": "night jazz lofi"},
]
MOOD_BY_KEY = {m["key"]: m for m in MOOD_DEFS}


class SpotifyMoodMetadataProvider(BaseMetadataProvider):
    """지금 이 무드에 어울리는 Spotify 플레이리스트 추천 + 검색 플러그인."""

    id = "spotify_mood"
    name = "스포티파이 무드"
    is_searchable = False

    config_schema = [
        {
            "key": "CLIENT_ID",
            "label": "Spotify Client ID",
            "type": "text",
            "required": True,
        },
        {
            "key": "CLIENT_SECRET",
            "label": "Spotify Client Secret",
            "type": "password",
            "required": True,
        },
        {
            "key": "MARKET",
            "label": "검색 지역(Market)",
            "type": "select",
            "default": "KR",
            "options": [
                {"value": "KR", "label": "한국"},
                {"value": "US", "label": "미국"},
                {"value": "JP", "label": "일본"},
                {"value": "GB", "label": "영국"},
            ],
        },
        {
            "key": "REDIRECT_URI",
            "label": "OAuth Redirect URI (선택, '내 플레이리스트' 기능용 - Spotify 앱에 등록한 값과 정확히 일치해야 함, 예: https://내도메인/callback)",
            "type": "text",
            "required": False,
        },
    ]

    dashboard_widget = {
        "title": "지금 이 무드",
        "subtitle": "시간대에 어울리는 Spotify 플레이리스트",
        "provider": "Spotify",
        "icon": "fa-brands fa-spotify",
        "limit": 4,
    }

    category_tab = {
        "title": "스포티파이 무드",
        "icon": "fa-brands fa-spotify",
        "order": 92,
    }

    update_manifest = {
        "enabled": True,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/leeyj/BookOasis_stable/main/sample_plugins/metadata/spotify_mood",
        "files": ["spotify_mood.py", "__init__.py", "VERSION"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": True,
    }

    # ------------------------------------------------------------------
    # 필수 계약 (검색형 메타데이터 기능은 사용하지 않음 - 대시보드/카테고리 전용)
    # ------------------------------------------------------------------
    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "스포티파이 무드 플러그인은 도서 메타데이터 적용을 지원하지 않습니다."

    # ------------------------------------------------------------------
    # 무드 판정
    # ------------------------------------------------------------------
    def _resolve_mood(self, mood_key=None):
        if mood_key and mood_key in MOOD_BY_KEY:
            return MOOD_BY_KEY[mood_key]
        from datetime import datetime

        hour = datetime.now().hour
        for mood in MOOD_DEFS:
            if hour in mood["hours"]:
                return mood
        return MOOD_DEFS[2]  # fallback: focus

    def _get_request_args(self):
        """카테고리 풀페이지에서 넘어오는 추가 쿼리 파라미터(mood/q/kind)를 안전하게 읽는다."""
        try:
            from flask import request

            return {
                "mood": (request.args.get("mood") or "").strip() or None,
                "q": (request.args.get("q") or "").strip() or None,
                "kind": (request.args.get("kind") or "playlist").strip() or "playlist",
                "mine": (request.args.get("mine") or "").strip() in ("1", "true"),
            }
        except Exception:
            return {"mood": None, "q": None, "kind": "playlist", "mine": False}

    # ------------------------------------------------------------------
    # Spotify Client Credentials 인증 + API 호출
    # ------------------------------------------------------------------
    def _token_cache_key(self, db_type, client_id):
        # CLIENT_ID를 캐시 키에 포함시켜, 사용자가 환경설정에서 자격증명을 바꾸면
        # 예전 CLIENT_ID로 발급받아 캐싱해둔 토큰이 아니라 즉시 새 토큰을 재발급받도록 한다.
        # (db_type만 키로 쓰면 자격증명을 바꿔도 옛 토큰이 계속 재사용되는 버그가 있었음)
        import hashlib

        client_fp = hashlib.sha256(client_id.encode("utf-8")).hexdigest()[:12]
        return f"token:{db_type}:{client_fp}"

    def _get_access_token(self, db_type, client_id, client_secret):
        cache_key = self._token_cache_key(db_type, client_id)
        cached = self.cache_get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                if data.get("token"):
                    logger.warning("[spotify_mood] 토큰 캐시 히트 (key=%s)", cache_key)
                    return data["token"]
            except Exception:
                pass

        logger.warning(
            "[spotify_mood] 토큰 신규 발급 요청 (client_id=%s..., key=%s)",
            client_id[:6], cache_key,
        )
        resp = requests.post(
            SPOTIFY_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            detail = ""
            try:
                body = resp.json()
                detail = body.get("error_description") or body.get("error") or ""
            except Exception:
                detail = (resp.text or "")[:200]
            logger.warning(
                "[spotify_mood] 토큰 발급 실패 status=%s detail=%s client_id=%s...",
                resp.status_code, detail, client_id[:6],
            )
            raise RuntimeError(
                f"Spotify 토큰 발급 실패 (status {resp.status_code}): {detail or '알 수 없는 오류'}"
            )
        payload = resp.json()
        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 3600)
        if token:
            self.cache_set(cache_key, json.dumps({"token": token}), ttl=max(60, expires_in - 60))
            logger.warning("[spotify_mood] 토큰 신규 발급 성공, %s초 캐싱 (key=%s)", expires_in, cache_key)
        return token

    def _spotify_get(self, db_type, client_id, client_secret, path, params=None, _retry=True):
        token = self._get_access_token(db_type, client_id, client_secret)
        if not token:
            raise RuntimeError("Spotify 인증 토큰을 발급받지 못했습니다. CLIENT_ID/CLIENT_SECRET을 확인해주세요.")

        logger.warning("[spotify_mood] Spotify 요청: %s params=%s", path, params)
        resp = requests.get(
            f"{SPOTIFY_API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=REQUEST_TIMEOUT,
        )
        logger.warning("[spotify_mood] Spotify 응답: status=%s", resp.status_code)
        if resp.status_code == 401 and _retry:
            logger.warning("[spotify_mood] 401 수신, 캐시된 토큰 폐기 후 1회 재시도 (key=%s)", self._token_cache_key(db_type, client_id))
            self.cache_delete(self._token_cache_key(db_type, client_id))
            return self._spotify_get(db_type, client_id, client_secret, path, params, _retry=False)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # OAuth Authorization Code Flow ("내 플레이리스트" 기능용, 서버당 계정 1개 공유)
    # ------------------------------------------------------------------
    def _is_admin_session(self):
        try:
            from flask import session

            return session.get("role") == "admin"
        except Exception:
            return False

    def _build_authorize_url(self, db_type, cfg):
        client_id = str(cfg.get("CLIENT_ID") or "").strip()
        redirect_uri = str(cfg.get("REDIRECT_URI") or "").strip()
        if not client_id or not redirect_uri:
            return None, "CLIENT_ID와 REDIRECT_URI를 먼저 환경설정에 입력해주세요."

        import secrets
        import urllib.parse
        from flask import session

        nonce = secrets.token_urlsafe(16)
        session["spotify_oauth_nonce"] = nonce
        state = f"{self.id}:{nonce}"

        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SPOTIFY_OAUTH_SCOPES,
            "state": state,
        }
        return f"{SPOTIFY_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}", None

    def handle_oauth_callback(self, db_type, code, state, error):
        """코어의 범용 OAuth 콜백 브릿지(GET /callback)가 state로 plugin_id를 보고 위임하는 지점."""
        if not self._is_admin_session():
            return {"success": False, "message": "관리자 계정으로 로그인한 상태에서만 연결할 수 있습니다."}

        if error:
            return {"success": False, "message": f"Spotify 인증이 거부되었습니다: {error}"}
        if not code:
            return {"success": False, "message": "인가 코드(code)가 없습니다."}

        try:
            from flask import session

            expected_nonce = session.pop("spotify_oauth_nonce", None)
            actual_nonce = state.split(":", 1)[1] if state and ":" in state else None
            if not expected_nonce or expected_nonce != actual_nonce:
                return {"success": False, "message": "요청이 만료되었거나 위조되었습니다. 다시 시도해주세요."}
        except Exception:
            return {"success": False, "message": "세션 확인 중 오류가 발생했습니다."}

        cfg = self.get_plugin_config(db_type, default={}) or {}
        client_id = str(cfg.get("CLIENT_ID") or "").strip()
        client_secret = str(cfg.get("CLIENT_SECRET") or "").strip()
        redirect_uri = str(cfg.get("REDIRECT_URI") or "").strip()
        if not client_id or not client_secret or not redirect_uri:
            return {"success": False, "message": "CLIENT_ID/CLIENT_SECRET/REDIRECT_URI 설정이 누락되었습니다."}

        resp = requests.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=(client_id, client_secret),
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            detail = ""
            try:
                body = resp.json()
                detail = body.get("error_description") or body.get("error") or ""
            except Exception:
                detail = (resp.text or "")[:200]
            logger.warning("[spotify_mood] OAuth 토큰 교환 실패 status=%s detail=%s", resp.status_code, detail)
            return {"success": False, "message": f"토큰 교환 실패 (status {resp.status_code}): {detail}"}

        payload = resp.json()
        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            return {"success": False, "message": "Spotify 응답에 refresh_token이 없습니다."}

        merged_cfg = dict(cfg)
        merged_cfg["REFRESH_TOKEN"] = refresh_token
        from services.plugin_service import PluginService

        ok, save_err = PluginService.save_plugin_config(db_type, self.id, merged_cfg)
        if not ok:
            return {"success": False, "message": f"설정 저장 실패: {save_err}"}

        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 3600)
        if access_token:
            self.cache_set(
                self._user_token_cache_key(db_type, client_id),
                json.dumps({"token": access_token}),
                ttl=max(60, expires_in - 60),
            )

        logger.warning("[spotify_mood] OAuth 연결 성공 (client_id=%s...)", client_id[:6])
        return {"success": True, "message": "Spotify 계정이 연결되었습니다! 이제 '내 플레이리스트'를 볼 수 있어요."}

    def _disconnect_oauth(self, db_type):
        cfg = self.get_plugin_config(db_type, default={}) or {}
        client_id = str(cfg.get("CLIENT_ID") or "").strip()
        if not cfg.get("REFRESH_TOKEN"):
            return {"success": True, "message": "이미 연결되어 있지 않습니다."}

        merged_cfg = dict(cfg)
        merged_cfg.pop("REFRESH_TOKEN", None)
        from services.plugin_service import PluginService

        ok, save_err = PluginService.save_plugin_config(db_type, self.id, merged_cfg)
        if not ok:
            return {"success": False, "error": f"설정 저장 실패: {save_err}"}

        if client_id:
            self.cache_delete(self._user_token_cache_key(db_type, client_id))
        return {"success": True, "message": "Spotify 계정 연결을 해제했습니다."}

    def _user_token_cache_key(self, db_type, client_id):
        import hashlib

        client_fp = hashlib.sha256(client_id.encode("utf-8")).hexdigest()[:12]
        return f"user_token:{db_type}:{client_fp}"

    def _get_user_access_token(self, db_type, client_id, client_secret, refresh_token):
        cache_key = self._user_token_cache_key(db_type, client_id)
        cached = self.cache_get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                if data.get("token"):
                    return data["token"]
            except Exception:
                pass

        resp = requests.post(
            SPOTIFY_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(client_id, client_secret),
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            detail = ""
            try:
                detail = resp.json().get("error_description") or ""
            except Exception:
                pass
            raise RuntimeError(f"Spotify 사용자 토큰 갱신 실패 (status {resp.status_code}): {detail}")

        payload = resp.json()
        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 3600)
        if access_token:
            self.cache_set(cache_key, json.dumps({"token": access_token}), ttl=max(60, expires_in - 60))

        # Spotify가 회전된 refresh_token을 새로 내려줄 때가 있다 - 그 경우 반드시 갱신 저장해야
        # 다음 갱신 시도에서 예전(무효화된) refresh_token으로 실패하지 않는다.
        new_refresh_token = payload.get("refresh_token")
        if new_refresh_token and new_refresh_token != refresh_token:
            cfg = self.get_plugin_config(db_type, default={}) or {}
            merged_cfg = dict(cfg)
            merged_cfg["REFRESH_TOKEN"] = new_refresh_token
            from services.plugin_service import PluginService

            PluginService.save_plugin_config(db_type, self.id, merged_cfg)

        return access_token

    def _search_my_playlists(self, db_type, client_id, client_secret, refresh_token, limit):
        token = self._get_user_access_token(db_type, client_id, client_secret, refresh_token)
        resp = requests.get(
            f"{SPOTIFY_API_BASE}/me/playlists",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": max(1, min(int(limit or 10), 10))},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        raw_items = (resp.json() or {}).get("items") or []
        items = [self._normalize_item("playlist", item) for item in raw_items]
        return [item for item in items if item]

    # ------------------------------------------------------------------
    # 검색 결과 -> 대시보드 카드 공통 필드(title/author/cover/link/publisher/pubDate)로 정규화
    # ------------------------------------------------------------------
    def _normalize_item(self, kind, raw):
        if not raw:
            return None

        if kind == "track":
            artists = ", ".join(a.get("name", "") for a in (raw.get("artists") or []) if a.get("name"))
            album = raw.get("album") or {}
            images = album.get("images") or []
            ms = int(raw.get("duration_ms") or 0)
            duration = f"{ms // 60000}:{(ms // 1000) % 60:02d}" if ms else ""
            return {
                "title": raw.get("name") or "제목 없음",
                "author": artists or "아티스트 미상",
                "cover": images[0]["url"] if images else "",
                "link": (raw.get("external_urls") or {}).get("spotify") or "#",
                "publisher": album.get("name") or "Spotify",
                "pubDate": duration,
                "spotify_id": raw.get("id"),
                "kind": "track",
            }

        if kind == "artist":
            images = raw.get("images") or []
            genres = ", ".join((raw.get("genres") or [])[:3])
            followers = (raw.get("followers") or {}).get("total") or 0
            return {
                "title": raw.get("name") or "제목 없음",
                "author": genres or "아티스트",
                "cover": images[0]["url"] if images else "",
                "link": (raw.get("external_urls") or {}).get("spotify") or "#",
                "publisher": "Spotify Artist",
                "pubDate": f"팔로워 {followers:,}명",
                "spotify_id": raw.get("id"),
                "kind": "artist",
            }

        if kind == "album":
            images = raw.get("images") or []
            artists = ", ".join(a.get("name", "") for a in (raw.get("artists") or []) if a.get("name"))
            return {
                "title": raw.get("name") or "제목 없음",
                "author": artists or "아티스트 미상",
                "cover": images[0]["url"] if images else "",
                "link": (raw.get("external_urls") or {}).get("spotify") or "#",
                "publisher": "Spotify Album",
                "pubDate": raw.get("release_date") or "",
                "spotify_id": raw.get("id"),
                "kind": "album",
            }

        # playlist (기본값)
        images = raw.get("images") or []
        owner = (raw.get("owner") or {}).get("display_name") or "Spotify"
        tracks_total = (raw.get("tracks") or {}).get("total") or 0
        return {
            "title": raw.get("name") or "제목 없음",
            "author": f"by {owner}",
            "cover": images[0]["url"] if images else "",
            "link": (raw.get("external_urls") or {}).get("spotify") or "#",
            "publisher": "Spotify Playlist",
            "pubDate": f"{tracks_total}곡",
            "description": (raw.get("description") or "").strip(),
            "spotify_id": raw.get("id"),
            "kind": "playlist",
        }

    def _search(self, db_type, client_id, client_secret, market, query, kind, limit):
        kind = kind if kind in ("playlist", "track", "artist", "album") else "playlist"
        params = {
            "q": query,
            "type": kind,
            # 실측 확인됨: Extended Quota Mode 승인을 받지 못한(Development Mode) 앱은
            # /v1/search의 limit이 11 이상이면 타입(playlist/track/artist/album) 전부
            # "Invalid limit" 400을 반환한다 - 10까지는 정상. market 파라미터는 무관했음
            # (이전에 market 제거로 우회했던 건 잘못된 진단이었음, 그냥 limit<=10로 클램프).
            "limit": max(1, min(int(limit or 10), 10)),
            "market": market or "KR",
        }
        data = self._spotify_get(
            db_type,
            client_id,
            client_secret,
            "/search",
            params=params,
        )
        bucket = data.get(f"{kind}s") or {}
        raw_items = bucket.get("items") or []
        items = [self._normalize_item(kind, item) for item in raw_items]
        return [item for item in items if item]

    # ------------------------------------------------------------------
    # 대시보드 위젯 & 카테고리 풀페이지 공용 데이터 엔드포인트
    # ------------------------------------------------------------------
    def get_dashboard_data(self, db_type, limit=10):
        cfg = self.get_plugin_config(db_type, default={}) or {}
        client_id = str(cfg.get("CLIENT_ID") or "").strip()
        client_secret = str(cfg.get("CLIENT_SECRET") or "").strip()
        market = str(cfg.get("MARKET") or "KR").strip()

        if not client_id or not client_secret:
            return {
                "success": False,
                "error": "Spotify CLIENT_ID/CLIENT_SECRET이 설정되지 않았습니다. 환경설정 > 플러그인에서 입력해주세요.",
            }

        args = self._get_request_args()
        refresh_token = str(cfg.get("REFRESH_TOKEN") or "").strip()
        connected = bool(refresh_token)

        try:
            if args["mine"]:
                if not connected:
                    return {
                        "success": False,
                        "error": "Spotify 계정이 연결되어 있지 않습니다. 'Spotify 계정 연결' 버튼을 먼저 눌러주세요.",
                        "connected": False,
                    }
                items = self._search_my_playlists(db_type, client_id, client_secret, refresh_token, limit)
                mood_label = "내 플레이리스트"
                mood_key = None
            elif args["q"]:
                items = self._search(db_type, client_id, client_secret, market, args["q"], args["kind"], limit)
                mood_label = f"검색: {args['q']}"
                mood_key = None
            else:
                mood = self._resolve_mood(args["mood"])
                items = self._search(db_type, client_id, client_secret, market, mood["query"], "playlist", limit)
                mood_label = mood["label"]
                mood_key = mood["key"]
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            detail = ""
            if e.response is not None:
                try:
                    body = e.response.json()
                    detail = (body.get("error") or {}).get("message") or ""
                except Exception:
                    detail = (e.response.text or "")[:200]
            logger.warning("[spotify_mood] Spotify API 오류 status=%s detail=%s", status, detail)
            return {"success": False, "error": f"Spotify API 오류 (status {status}): {detail or '알 수 없는 오류'}"}
        except Exception as e:
            logger.warning("[spotify_mood] 요청 실패: %s", e)
            return {"success": False, "error": f"Spotify 요청 실패: {e}"}

        return {
            "success": True,
            "mood": mood_label,
            "mood_key": mood_key,
            "moods": [{"key": m["key"], "label": m["label"]} for m in MOOD_DEFS],
            "items": items[: max(1, int(limit or 10))],
            "connected": connected,
        }

    # ------------------------------------------------------------------
    # 보너스: 도서 컨텍스트 메뉴에서 바로 "이 책과 어울리는 플레이리스트 찾기"
    # ------------------------------------------------------------------
    def get_context_menu_items(self, db_type, context):
        return [
            {
                "id": "spotify_mood_open_search",
                "label": "이 책과 어울리는 플레이리스트 찾기",
                "icon": "fa-brands fa-spotify",
            }
        ]

    def run_context_menu_action(self, db_type, action_id, context):
        # 도서 컨텍스트 메뉴 액션
        if action_id == "spotify_mood_open_search":
            title = (context or {}).get("book_title") or ""
            if not title:
                return {"success": False, "error": "책 제목 정보가 없습니다."}

            import urllib.parse

            url = "https://open.spotify.com/search/" + urllib.parse.quote(f"{title} playlist")
            return {"success": True, "message": "Spotify 검색 결과를 새 탭으로 엽니다.", "open_url": url}

        # 카테고리 풀페이지의 "Spotify 계정 연결" 버튼이 호출하는 범용 액션
        # (플러그인이 자체 라우트를 만들 수 없어, 이미 있는 컨텍스트 메뉴 RPC 다리를 재사용)
        if action_id == "spotify_oauth_start":
            if not self._is_admin_session():
                return {"success": False, "error": "관리자만 Spotify 계정을 연결할 수 있습니다."}
            cfg = self.get_plugin_config(db_type, default={}) or {}
            url, err = self._build_authorize_url(db_type, cfg)
            if err:
                return {"success": False, "error": err}
            return {"success": True, "open_url": url}

        if action_id == "spotify_oauth_disconnect":
            if not self._is_admin_session():
                return {"success": False, "error": "관리자만 연결을 해제할 수 있습니다."}
            return self._disconnect_oauth(db_type)

        return {"success": False, "error": f"지원하지 않는 액션입니다: {action_id}"}
