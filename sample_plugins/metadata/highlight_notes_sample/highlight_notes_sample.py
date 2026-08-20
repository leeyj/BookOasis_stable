# -*- coding: utf-8 -*-
"""
highlight_notes_sample.py — EPUB/TXT 뷰어 하이라이트 컨텍스트 메뉴 확장의 최소 샘플.

이 플러그인이 보여주는 것 (docs/guide_plugins.md 7장 "하이라이트(주석) 컨텍스트 메뉴
확장 계약"의 살아있는 예제):

  1. get_annotation_context_menu_items() / run_annotation_context_menu_action() —
     하이라이트를 우클릭(PC)/롱프레스(모바일)했을 때 뜨는 메뉴에 항목을 추가하는 계약.
  2. "prompt" 응답 왕복 — run_annotation_context_menu_action()은 서버에서 실행되는
     헤드리스 함수라 직접 입력창을 띄울 수 없다. 그래서 1단계 호출에서는
     "이런 입력창을 띄워 달라"는 요청만 반환하고, 프런트가 모달로 값을 받아 같은
     action_id로 다시 호출해주면 그때(2단계) 실제로 저장을 수행한다.
  3. 코어 DB를 전혀 쓰지 않는 저장 방식 — 메모는 book_annotations 테이블의 note
     컬럼이 아니라, 이 플러그인 자신의 JSONL(JSON Lines) 파일에 저장한다. 이는
     의도적인 설계 선택이다: 코어는 "하이라이트가 어디 있는지"만 책임지고,
     "그 하이라이트로 뭘 할지"는 플러그인이 원하는 방식(JSONL이든 SQLite든 외부
     API 호출이든) 자유롭게 정하면 된다는 걸 보여주기 위함.
  4. "marker" 응답 필드 — 메모를 플러그인 자체 저장소에 감춰두면, 사용자가 뷰어
     화면만 보고는 "이 하이라이트에 메모가 있는지" 전혀 알 수 없는 문제가 생긴다.
     그래서 run_annotation_context_menu_action()의 반환값에 'marker': '*' 를
     실어 보내면, 코어가 book_annotations.plugin_marker 컬럼에 그 값을 저장하고
     하이라이트 바로 뒤에 위첨자로 그려준다 — 실제 메모 내용은 여전히 코어가
     모르는 채로, "뭔가 달려있다"는 시각적 신호만 코어에게 위임하는 것이다.
     get_annotation_context_menu_items()는 메뉴가 열릴 때마다 새로 호출되므로,
     거기서 자체 저장소를 조회해 메뉴 라벨을 "메모 작성"/"메모 보기·수정"으로
     바꿔주는 것과 합쳐지면 "저장은 됐는데 다시 볼 방법이 없다"는 문제가 해결된다.

주의: 이건 학습/시작용 "샘플"이다. 실무 플러그인이라면 동시쓰기 경합, 파일 파손
대비, 더 정교한 조회(예: 특정 책의 메모만 필터링하는 API 엔드포인트 노출) 등을
추가로 고려해야 한다.
"""
import json
import os
import time

from plugins.metadata.base import BaseMetadataProvider


class HighlightNotesSampleProvider(BaseMetadataProvider):
    """하이라이트에 메모를 남겨 JSONL 파일에 저장하는 샘플 플러그인."""

    id = "highlight_notes_sample"
    name = "하이라이트 메모 (샘플)"
    # 메타데이터 검색/적용 기능은 제공하지 않는 플러그인이므로 검색 대상에서 제외
    is_searchable = False
    config_schema = []

    # ────────────────────────────────────────────────────────────────
    # BaseMetadataProvider 필수 계약(search/apply)은 이 플러그인의 목적과
    # 무관하지만, 추상 메서드라 어떤 구현이든 반드시 있어야 한다. naver_book.py
    # 샘플과 동일하게 "지원하지 않음"을 명확히 반환하는 최소 구현만 둔다.
    # ────────────────────────────────────────────────────────────────
    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "하이라이트 메모 샘플 플러그인은 메타데이터 적용을 지원하지 않습니다."

    # ────────────────────────────────────────────────────────────────
    # JSONL 저장소 헬퍼
    # ────────────────────────────────────────────────────────────────
    def _get_storage_path(self):
        """메모를 저장할 JSONL 파일 경로.

        이 플러그인 폴더(__file__ 기준) 바로 아래에 저장한다 — 별도 설정 없이
        플러그인만 넣으면 바로 동작하도록 자기완결적으로 만들기 위함이다.
        단, update_manifest(원격 자동 업데이트)를 쓰는 실제 플러그인이라면 그
        files 목록에 이 데이터 파일이 포함되지 않도록 주의해야 한다 — 포함되면
        업데이트할 때마다 저장해둔 메모가 원격 소스로 덮어써질 수 있다.
        """
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(plugin_dir, "highlight_notes.jsonl")

    def _append_note(self, record):
        """레코드 한 줄을 JSONL 파일 끝에 추가한다.

        JSON Lines는 "한 줄 = 완결된 JSON 객체 1개"인 append-only 로그 포맷이라,
        전체 파일을 파싱하지 않고도 안전하게 이어붙일 수 있다(동시 저장 시
        레이스가 있을 수 있지만, 샘플 범위에서는 다루지 않는다).
        """
        path = self._get_storage_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _find_latest_note(self, annotation_id):
        """같은 annotation_id로 저장된 기록 중 가장 최근 것의 메모 텍스트를 찾는다.
        (프롬프트 입력창을 다시 열 때 이전에 쓴 메모를 기본값으로 채워주기 위함)
        """
        path = self._get_storage_path()
        if not os.path.exists(path):
            return None

        latest_note = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except (ValueError, TypeError):
                        # 손상된 줄 하나 때문에 전체 조회가 실패하지 않도록 건너뜀
                        continue
                    if str(record.get("annotation_id")) == str(annotation_id):
                        latest_note = record.get("note")
        except OSError:
            return None
        return latest_note

    # ────────────────────────────────────────────────────────────────
    # 하이라이트 컨텍스트 메뉴 확장 계약
    # ────────────────────────────────────────────────────────────────
    def get_annotation_context_menu_items(self, db_type, context):
        """하이라이트 우클릭/롱프레스 메뉴에 노출할 항목 목록.

        여러 플러그인이 동시에 활성화돼 있으면 코어가 plugin_name 기준으로
        자동 그룹핑해서 보여주므로, 이 메서드는 "내 플러그인이 제공하는 항목"만
        신경 쓰면 된다.

        이 메서드는 메뉴가 열릴 때마다(즉 사용자가 우클릭/롱프레스할 때마다)
        매번 새로 호출되므로, 여기서 self._find_latest_note()로 기존 메모
        존재 여부를 확인해 라벨을 "메모 작성"/"메모 보기·수정"으로 바꿔준다 —
        전에 이미 저장된 하이라이트인지 사용자가 메뉴만 보고도 알 수 있게.
        """
        annotation_id = context.get("annotation_id")
        has_note = bool(annotation_id and self._find_latest_note(annotation_id))
        return [
            {
                "id": "add_note",
                "label": "메모 보기 · 수정 (샘플)" if has_note else "메모 작성 (샘플)",
                "icon": "fa-solid fa-note-sticky",
            }
        ]

    def run_annotation_context_menu_action(self, db_type, action_id, context):
        """메뉴 항목 클릭 시 실행되는 액션.

        핵심은 context 안에 'prompt_value' 키가 있는지로 "1단계(입력 요청)"와
        "2단계(입력값을 받아 실제 저장)"를 구분하는 것이다:

          1단계 — 사용자가 메뉴에서 "메모 작성"을 막 클릭한 시점.
                  context에는 아직 사용자가 입력한 텍스트가 없다.
                  → 입력창을 띄워 달라는 'prompt' 요청을 반환하고 끝낸다.

          2단계 — 프런트가 그 요청을 보고 모달을 띄워 사용자 입력을 받은 뒤,
                  같은 action_id('add_note')로 이 메서드를 다시 호출한다.
                  이번엔 context['prompt_value']에 사용자가 입력한 문자열이
                  들어있다. → 이제 실제로 저장을 수행한다.

        사용자가 입력 모달에서 "취소"를 누르면 코어가 알아서 재호출을 하지
        않으므로, 이 메서드 안에서 취소 케이스를 별도로 처리할 필요는 없다.
        """
        if action_id != "add_note":
            return {"success": False, "error": f"지원하지 않는 액션입니다: {action_id}"}

        annotation_id = context.get("annotation_id")
        if not annotation_id:
            return {"success": False, "error": "annotation_id가 없습니다."}

        # ── 1단계: 아직 사용자 입력이 없으면, 입력창을 띄워 달라고 요청한다 ──
        if "prompt_value" not in context:
            existing_note = self._find_latest_note(annotation_id)
            return {
                "success": True,
                "prompt": {
                    "title": "하이라이트 메모 작성",
                    "message": "이 하이라이트에 대한 생각을 자유롭게 적어보세요.",
                    "placeholder": "예: 이 대사가 복선인 것 같다...",
                    # 이전에 같은 하이라이트에 남겨둔 메모가 있으면 기본값으로 채워
                    # "수정하는 느낌"이 나게 한다 (실제로는 새 기록이 하나 더
                    # 추가되는 append-only 방식이지만, 사용자 입장에서는 이전 내용을
                    # 이어서 고치는 것처럼 보이는 게 자연스럽다).
                    "default_value": existing_note or "",
                    "multiline": True,
                    "submit_label": "저장",
                },
            }

        # ── 2단계: 사용자가 입력한 값을 받아 실제로 저장한다 ──
        note_text = str(context.get("prompt_value") or "").strip()
        if not note_text:
            return {"success": False, "error": "메모 내용이 비어 있습니다."}

        record = {
            "annotation_id": annotation_id,
            "book_id": context.get("book_id"),
            "book_title": context.get("book_title"),
            "series_name": context.get("series_name"),
            "format": context.get("format"),
            "chapter_idx": context.get("chapter_idx"),
            "quote": context.get("quote"),
            "note": note_text,
            # 코어의 book_annotations.updated_at과는 별개로, 이 플러그인 자신의
            # 저장 이력을 남기기 위한 타임스탬프(epoch seconds).
            "saved_at": time.time(),
        }

        try:
            self._append_note(record)
        except OSError as e:
            return {"success": False, "error": f"메모 저장 중 오류가 발생했습니다: {e}"}

        # 'marker' 키를 응답에 넣으면, 코어가 이 하이라이트의 book_annotations.plugin_marker
        # 컬럼에 그 값을 저장하고 본문 위 하이라이트 바로 뒤에 위첨자로 그려준다. 실제 메모
        # 내용은 여전히 이 플러그인의 JSONL 파일에만 있고 코어 DB에는 전혀 저장되지 않는다 —
        # 코어 입장에선 "이 하이라이트에 뭔가 달려있다"는 사실만 알 뿐, 내용은 모른다.
        # 값을 빈 문자열/None으로 반환하면 반대로 표시를 지울 수 있다(이 샘플에서는 메모를
        # 지우는 액션을 따로 만들지 않아서 쓰이지 않지만, 실전 플러그인에서는 "메모 삭제"
        # 액션의 응답에 {'marker': None}을 넣어 표시를 함께 없애면 된다).
        return {"success": True, "message": "메모가 저장되었습니다 (JSONL).", "marker": "*"}
