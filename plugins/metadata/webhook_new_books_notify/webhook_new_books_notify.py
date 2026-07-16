# -*- coding: utf-8 -*-
import json
import urllib.parse
import urllib.request

from plugins.metadata.base import BaseMetadataProvider


class WebhookNewBooksNotifyMetadataProvider(BaseMetadataProvider):
    """Example plugin: send scan new-book notifications to configurable webhook targets."""

    id = "webhook_new_books_notify"
    name = "신규도서 웹훅 알림"
    is_searchable = False
    config_schema = [
        {
            "key": "ENABLE_SCAN_WEBHOOK_NOTIFY",
            "label": "신규도서 웹훅 알림 활성화",
            "type": "checkbox",
            "default": False,
            "description": "활성화하면 스캔 종료 후 신규도서 감지 시 웹훅으로 알림을 전송합니다.",
        },
        {
            "key": "MAX_SAMPLE_TITLES",
            "label": "알림에 포함할 샘플 제목 수",
            "type": "number",
            "default": 10,
            "description": "신규도서 제목 샘플 표시 개수입니다.",
        },
        {
            "key": "DISCORD_WEBHOOK_URL",
            "label": "Discord Webhook URL(하위호환)",
            "type": "text",
            "required": False,
            "description": "WEBHOOK_TARGETS_JSON 미사용 시 하위호환용 디스코드 URL입니다.",
        },
        {
            "key": "WEBHOOK_TARGETS_JSON",
            "label": "Webhook Targets JSON",
            "type": "text",
            "required": False,
            "description": "예: [{\"name\":\"discord\",\"url\":\"https://...\",\"format\":\"discord\"},{\"name\":\"telegram\",\"url\":\"https://api.telegram.org/bot.../sendMessage\",\"format\":\"telegram\",\"chat_id\":\"123456\"}]",
        },
        {
            "key": "CUSTOM_EVENT_PAYLOAD_JSON",
            "label": "Custom Event Payload JSON(optional)",
            "type": "text",
            "required": False,
            "description": "format=custom 대상에 사용할 JSON 템플릿. 플레이스홀더: {{event}}, {{library_name}}, {{new_books_count}}, {{sample_titles_csv}}",
        },
        {
            "key": "REQUEST_TIMEOUT_SEC",
            "label": "요청 타임아웃(초)",
            "type": "number",
            "default": 5,
            "description": "Webhook 요청 타임아웃(초)입니다.",
        },
    ]

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 메타데이터 적용을 지원하지 않습니다."

    def _is_enabled(self, db_type):
        cfg = self._get_config(db_type)
        raw = cfg.get("ENABLE_SCAN_WEBHOOK_NOTIFY")
        if raw is None:
            # backward compatibility
            raw = cfg.get("ENABLE_SCAN_DISCORD_NOTIFY", False)
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "y", "yes", "on")

    def _sample_limit(self, db_type):
        cfg = self._get_config(db_type)
        raw = cfg.get("MAX_SAMPLE_TITLES", 10)
        try:
            n = int(raw)
        except Exception:
            n = 10
        return max(1, min(20, n))

    def _get_config(self, db_type):
        cfg = self.get_plugin_config(db_type, default={}) or {}
        if cfg:
            return cfg

        # Legacy plugin id fallback for migration compatibility.
        gateway = self.get_db_gateway(db_type)
        legacy = gateway.get_plugin_config("discord_new_books_notify", default={}) or {}
        return legacy

    def _webhook_url(self, db_type):
        cfg = self._get_config(db_type)
        url = str(cfg.get("DISCORD_WEBHOOK_URL") or "").strip()
        if not url.startswith("https://"):
            return ""
        return url

    def _parse_json(self, raw, default):
        try:
            return json.loads(raw)
        except Exception:
            return default

    def _targets(self, db_type):
        cfg = self._get_config(db_type)
        raw = str(cfg.get("WEBHOOK_TARGETS_JSON") or "").strip()
        parsed = self._parse_json(raw, []) if raw else []

        targets = []
        if isinstance(parsed, dict):
            parsed = [parsed]

        if isinstance(parsed, list):
            for t in parsed:
                if not isinstance(t, dict):
                    continue
                url = str(t.get("url") or "").strip()
                if not url.startswith("http://") and not url.startswith("https://"):
                    continue
                targets.append(t)

        # backward compatibility fallback
        if not targets:
            fallback_url = self._webhook_url(db_type)
            if fallback_url:
                targets.append({
                    "name": "discord",
                    "url": fallback_url,
                    "format": "discord",
                })

        return targets

    def _custom_payload_template(self, db_type):
        cfg = self._get_config(db_type)
        raw = str(cfg.get("CUSTOM_EVENT_PAYLOAD_JSON") or "").strip()
        if not raw:
            return None
        parsed = self._parse_json(raw, None)
        return parsed if isinstance(parsed, (dict, list)) else None

    def _timeout_sec(self, db_type):
        cfg = self._get_config(db_type)
        raw = cfg.get("REQUEST_TIMEOUT_SEC", 5)
        try:
            v = float(raw)
        except Exception:
            v = 5.0
        return max(1.0, min(30.0, v))

    def _read_dot_path(self, obj, path):
        cur = obj
        for key in str(path or "").split("."):
            key = key.strip()
            if not key:
                continue
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur.get(key)
        return cur

    def _render_template(self, data, ctx):
        if isinstance(data, dict):
            return {k: self._render_template(v, ctx) for k, v in data.items()}
        if isinstance(data, list):
            return [self._render_template(v, ctx) for v in data]
        if isinstance(data, str):
            out = data
            for k, v in ctx.items():
                out = out.replace("{{" + k + "}}", str(v))
            return out
        return data

    def _build_context(self, event_payload):
        payload = event_payload or {}
        sample_titles = payload.get("sample_titles") or []
        if not isinstance(sample_titles, list):
            sample_titles = []
        csv = ", ".join(str(t).strip() for t in sample_titles if str(t).strip())
        return {
            "event": "scan.new_books_detected",
            "db_type": payload.get("db_type", ""),
            "library_id": payload.get("library_id", ""),
            "library_name": payload.get("library_name", ""),
            "new_books_count": payload.get("new_books_count", 0),
            "sample_titles_csv": csv,
        }

    def _build_body_for_target(self, db_type, target, event_payload):
        channel_format = str(target.get("format") or "generic").strip().lower()
        title = "[BookOasis] scan.new_books_detected"
        compact = json.dumps(event_payload or {}, ensure_ascii=False)

        if channel_format == "discord":
            return {
                "username": "BookOasis",
                "content": f"{title}\n{compact[:1700]}",
            }

        if channel_format == "slack":
            return {
                "text": f"{title}\n{compact[:3000]}",
            }

        if channel_format == "telegram":
            body = {
                "text": f"{title}\n{compact[:3500]}",
                "disable_web_page_preview": True,
            }
            chat_id = str(target.get("chat_id") or "").strip()
            if chat_id:
                body["chat_id"] = chat_id
            return body

        if channel_format == "custom":
            template = target.get("body")
            if template is None:
                template = self._custom_payload_template(db_type)
            if template is not None:
                return self._render_template(template, self._build_context(event_payload))

        return {
            "source": "bookoasis",
            "event": "scan.new_books_detected",
            "payload": event_payload or {},
        }

    def _send_target(self, db_type, target, event_payload):
        url = str(target.get("url") or "").strip()
        method = str(target.get("method") or "POST").strip().upper()
        headers = target.get("headers") if isinstance(target.get("headers"), dict) else {}
        headers = dict(headers)
        body = self._build_body_for_target(db_type, target, event_payload)

        req_url = url
        req_data = None
        if method == "GET":
            query = urllib.parse.urlencode({"payload": json.dumps(body, ensure_ascii=False)})
            sep = "&" if "?" in req_url else "?"
            req_url = f"{req_url}{sep}{query}"
        else:
            headers.setdefault("Content-Type", "application/json")
            req_data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(req_url, data=req_data, headers=headers, method=method)

        with urllib.request.urlopen(req, timeout=self._timeout_sec(db_type)) as resp:
            code = getattr(resp, "status", 200)
            response_text = ""
            response_json = None
            try:
                response_text = resp.read().decode("utf-8", errors="ignore")
                response_json = self._parse_json(response_text, None)
            except Exception:
                pass

            if code < 200 or code >= 300:
                return {
                    "success": False,
                    "failed": 1,
                    "sent": 0,
                    "error": f"HTTP {code}",
                    "response": response_text[:500],
                }

            success_path = str(target.get("success_path") or "").strip()
            if success_path and isinstance(response_json, dict):
                if not bool(self._read_dot_path(response_json, success_path)):
                    return {
                        "success": False,
                        "failed": 1,
                        "sent": 0,
                        "error": f"success_path false: {success_path}",
                        "response": response_json,
                    }

            return {
                "success": True,
                "failed": 0,
                "sent": 1,
                "status": code,
                "response": response_json if response_json is not None else response_text[:500],
            }

    def on_scan_new_books_detected(self, db_type, payload):
        if not self._is_enabled(db_type):
            return {
                "success": True,
                "skipped": True,
                "message": "plugin config ENABLE_SCAN_WEBHOOK_NOTIFY (or legacy ENABLE_SCAN_DISCORD_NOTIFY) is false",
            }

        targets = self._targets(db_type)
        if not targets:
            return {
                "success": False,
                "skipped": True,
                "message": "WEBHOOK_TARGETS_JSON or DISCORD_WEBHOOK_URL is missing/invalid",
            }

        book_count = int((payload or {}).get("new_books_count") or 0)
        if book_count <= 0:
            return {"success": True, "skipped": True, "message": "no new books"}

        sample_titles = list((payload or {}).get("sample_titles") or [])
        sample_titles = [str(t).strip() for t in sample_titles if str(t).strip()]
        sample_titles = sample_titles[: self._sample_limit(db_type)]

        content = {
            "db_type": (payload or {}).get("db_type"),
            "library_id": (payload or {}).get("library_id"),
            "library_name": (payload or {}).get("library_name"),
            "new_books_count": book_count,
            "sample_titles": sample_titles,
        }

        sent = 0
        failed = 0
        errors = []
        details = []

        for target in targets:
            target_name = str(target.get("name") or target.get("format") or "target").strip()
            try:
                result = self._send_target(db_type, target, content)
                details.append({"target": target_name, "result": result})
                if result.get("success"):
                    sent += 1
                else:
                    failed += 1
                    errors.append(f"{target_name}: {result.get('error', 'send failed')}")
            except Exception as exc:
                failed += 1
                errors.append(f"{target_name}: {exc}")
                details.append({"target": target_name, "result": {"success": False, "error": str(exc)}})

        return {
            "success": failed == 0,
            "sent": sent,
            "failed": failed,
            "errors": errors,
            "details": details,
        }
