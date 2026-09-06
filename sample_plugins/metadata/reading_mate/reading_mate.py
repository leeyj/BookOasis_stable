# -*- coding: utf-8 -*-
"""
reading_mate.py -- 화면 우측 하단에 캐릭터를 띄워두고, 클릭하면 채팅창이 열려
LLM과 대화하듯 내 서재의 책을 추천받는 "오버레이 마스코트" 샘플 플러그인.

- BookOasis 코어에는 "부팅 시 페이지 전역에 무언가를 주입하는" 훅이 없다. 그래서
  이 마스코트는 사이드바의 category_tab(전용 탭)을 사용자가 최초 1회 열 때
  script.js가 실행되면서 마운트되고, spotify_mood 샘플의 플로팅 플레이어와 동일한
  방식으로 자기 자신을 #library-plugin-custom-view 밖(document.body)에 옮겨 붙여서
  다른 탭으로 이동해도 계속 화면에 남아있게 만든다. 이 한계(세션 중 탭을 한 번도
  열지 않으면 마스코트도 뜨지 않음)는 docs 가이드에 명시했다.
- LLM 호출은 반드시 서버(이 파일)에서만 한다. API 키를 프론트엔드로 절대 내려주지
  않는다 (get_dashboard_data()가 유일한 백엔드 진입점이라 자연히 그렇게 됨).
- config_schema로 어떤 OpenAI 호환 채팅 API든(OpenAI, 로컬 Ollama/LM Studio,
  자체 게이트웨이 등) BASE_URL만 바꿔서 붙일 수 있게 했다.
"""
import json
import logging

import requests

from plugins.metadata.base import BaseMetadataProvider

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20
# 채팅 한 턴이 너무 길어지거나 히스토리가 무한정 쌓여 LLM 비용이 새는 것을 막기 위한 캡.
MAX_MESSAGE_CHARS = 500
MAX_HISTORY_TURNS = 8
LIBRARY_SAMPLE_LIMIT = 30


class ReadingMateMetadataProvider(BaseMetadataProvider):
    """우측 하단 오버레이 캐릭터 + LLM 채팅 기반 도서 추천 플러그인."""

    id = "reading_mate"
    name = "독서메이트 (오버레이 마스코트)"
    is_searchable = False

    config_schema = [
        {
            "key": "LLM_API_KEY",
            "label": "LLM API Key",
            "type": "password",
            "required": True,
        },
        {
            "key": "LLM_BASE_URL",
            "label": "LLM API Base URL (OpenAI 호환 /chat/completions 엔드포인트를 쓰는 서비스면 무엇이든 가능 - OpenAI, 로컬 Ollama/LM Studio, 자체 게이트웨이 등)",
            "type": "text",
            "default": "https://api.openai.com/v1",
            "required": True,
        },
        {
            "key": "LLM_MODEL",
            "label": "모델 이름",
            "type": "text",
            "default": "gpt-4o-mini",
            "required": True,
        },
        {
            "key": "CHARACTER_NAME",
            "label": "캐릭터 이름",
            "type": "text",
            "default": "책비서",
        },
        {
            "key": "CHARACTER_IMAGE_URL",
            "label": "캐릭터 이미지 URL (비워두면 기본 이모지로 대체)",
            "type": "text",
            "required": False,
        },
    ]

    # 대시보드 카드는 쓰지 않고, 사이드바 전용 탭 하나만 사용한다. 이 탭은
    # "마스코트를 처음 켜는 자리 + 설정 안내" 역할이고, 실제 마스코트/채팅 UI는
    # script.js가 document.body에 직접 붙인다 (아래 index.html/script.js 참고).
    category_tab = {
        "title": "독서메이트",
        "icon": "fa-solid fa-comment-dots",
        "order": 95,
        "sessions": "general",  # 도서 추천이므로 오디오북/비디오/성인 세션에는 노출하지 않음
    }

    update_manifest = {
        "enabled": True,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/leeyj/BookOasis_stable/main/sample_plugins/metadata/reading_mate",
        "files": ["reading_mate.py", "__init__.py", "VERSION"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": True,
    }

    # ------------------------------------------------------------------
    # 필수 계약 (검색형 메타데이터 기능은 사용하지 않음 - 오버레이 챗봇 전용)
    # ------------------------------------------------------------------
    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "독서메이트 플러그인은 도서 메타데이터 적용을 지원하지 않습니다."

    # ------------------------------------------------------------------
    # 요청 파라미터 파싱
    # ------------------------------------------------------------------
    def _get_request_args(self):
        try:
            from flask import request

            message = (request.args.get("message") or "").strip()[:MAX_MESSAGE_CHARS]

            history = []
            raw_history = request.args.get("history")
            if raw_history:
                try:
                    parsed = json.loads(raw_history)
                    if isinstance(parsed, list):
                        for turn in parsed[-MAX_HISTORY_TURNS:]:
                            role = turn.get("role")
                            content = str(turn.get("content") or "")[:MAX_MESSAGE_CHARS]
                            if role in ("user", "assistant") and content:
                                history.append({"role": role, "content": content})
                except Exception:
                    history = []

            return {"message": message, "history": history}
        except Exception:
            return {"message": "", "history": []}

    # ------------------------------------------------------------------
    # 내 서재 샘플 -> LLM에게 "실제로 이 서재에 있는 책만" 추천하게 근거로 제공
    # ------------------------------------------------------------------
    def _sample_library(self, db_type):
        try:
            gateway = self.get_db_gateway(db_type)
            rows = gateway.fetch_all(
                """
                SELECT title, author FROM books
                WHERE COALESCE(is_deleted, 0) = 0
                ORDER BY id DESC
                LIMIT ?
                """,
                (LIBRARY_SAMPLE_LIMIT,),
            )
            return [
                {"title": r.get("title") or "", "author": r.get("author") or ""}
                for r in (rows or [])
                if r.get("title")
            ]
        except Exception as e:
            logger.warning("[reading_mate] 서재 샘플 조회 실패: %s", e)
            return []

    def _build_system_prompt(self, character_name, library_sample):
        lines = [
            f"너는 '{character_name}'라는 이름의 친근한 독서 도우미 캐릭터야.",
            "사용자의 홈 서버 서재에 있는 책 중에서만 골라 짧고 다정하게 추천해.",
            "모르는 책을 지어내지 말고, 아래 목록에 없는 책이 필요하면 '서재에서 비슷한 걸 못 찾았어요'라고 솔직히 말해.",
            "답변은 채팅 말풍선에 들어가므로 3~4문장 이내로 짧게 유지해.",
            "특별한 언급이 없으면 한국어로 답해.",
        ]
        if library_sample:
            lines.append("현재 서재에 있는 책 (일부):")
            for book in library_sample:
                author = f" - {book['author']}" if book.get("author") else ""
                lines.append(f"- {book['title']}{author}")
        else:
            lines.append("현재 서재 정보를 불러오지 못했으니, 일반적인 독서 취향만 물어보며 대화를 이어가.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM 호출 (OpenAI 호환 /chat/completions 계약)
    # ------------------------------------------------------------------
    def _call_llm(self, base_url, api_key, model, messages):
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            detail = ""
            try:
                body = resp.json()
                detail = (body.get("error") or {}).get("message") or str(body)
            except Exception:
                detail = (resp.text or "")[:200]
            raise RuntimeError(f"status {resp.status_code}: {detail}")

        payload = resp.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM 응답에 choices가 없습니다.")
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("LLM 응답이 비어 있습니다.")
        return content

    # ------------------------------------------------------------------
    # 채팅 한 턴 처리 - 마스코트 위젯의 유일한 백엔드 진입점
    # (플러그인은 자체 라우트를 만들 수 없어, dashboard_widget 데이터 엔드포인트를
    #  범용 RPC로 재사용한다 - spotify_mood 샘플과 동일한 패턴)
    # ------------------------------------------------------------------
    def get_dashboard_data(self, db_type, limit=10):
        cfg = self.get_plugin_config(db_type, default={}) or {}
        api_key = str(cfg.get("LLM_API_KEY") or "").strip()
        base_url = str(cfg.get("LLM_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
        model = str(cfg.get("LLM_MODEL") or "gpt-4o-mini").strip()
        character_name = str(cfg.get("CHARACTER_NAME") or "책비서").strip()
        character_image_url = str(cfg.get("CHARACTER_IMAGE_URL") or "").strip()

        if not api_key:
            return {
                "success": False,
                "error": "LLM_API_KEY가 설정되지 않았습니다. 환경설정 > 플러그인에서 입력해주세요.",
            }

        args = self._get_request_args()

        if not args["message"]:
            # 초기 진입(메시지 없이 호출) - 인사말만 돌려준다.
            return {
                "success": True,
                "reply": f"안녕! 나는 {character_name}야. 요즘 어떤 분위기의 책이 끌려?",
                "character_name": character_name,
                "character_image_url": character_image_url,
            }

        library_sample = self._sample_library(db_type)
        system_prompt = self._build_system_prompt(character_name, library_sample)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(args["history"])
        messages.append({"role": "user", "content": args["message"]})

        try:
            reply = self._call_llm(base_url, api_key, model, messages)
        except Exception as e:
            logger.warning("[reading_mate] LLM 호출 실패: %s", e)
            return {"success": False, "error": f"LLM 호출에 실패했어요: {e}"}

        return {
            "success": True,
            "reply": reply,
            "character_name": character_name,
            "character_image_url": character_image_url,
        }
