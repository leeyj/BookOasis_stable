# -*- coding: utf-8 -*-
"""
series_official_relations.py - 커뮤니티가 공유하는 시리즈 관계 CSV(series_title, related_title,
relation_type 3컬럼)를 읽어, 우리 라이브러리 시리즈명과 정규화 후 정확 일치하는 것만 골라
"공식 연관작"(시퀄/프리퀄/스핀오프/외전/각색/세계관 공유 등)을 detail_sidebar_widget +
smart_recommend_widget 계약으로 노출하는 플러그인.

원래는 원본 큐레이션 DB(4.5GB짜리 Kitsu/AniList/MangaUpdates/ANN 통합 SQLite) 전체를 매번
열어서 id 인덱스를 만들고, state='active' 필터링과 중복/모호 타이틀 판별까지 우리 쪽에서
직접 했었다. 하지만 이 판별에 필요한 정보(state 컬럼 등)는 원본 큐레이터가 이미 갖고 있고
그쪽에서 한 번만 처리하면 끝나는 일이라, 매번 4.5GB를 열어 반복 계산할 이유가 없다고 판단해
"이미 정제된 title-to-title 관계 그래프"만 받는 방식으로 단순화했다 - CSV 하나로 모든 데이터
제공자를 강제하기보다, "읽기" 단계(_read_relation_rows)만 교체 가능한 어댑터로 열어뒀다:
CSV를 만들기 번거로운 데이터 소스를 가진 사람은 이 메서드 하나만 자기 방식(자기 DB 직접
쿼리, API 호출 등)으로 갈아끼워 포크하면 되고, 나머지(우리 라이브러리와의 매칭/저장/위젯
노출)는 그대로 재사용된다 - 자세한 확장 지점은 "동기화 알고리즘" 섹션 주석 참고.

데이터는 플러그인 전용 테이블(plugin_series_official_relations, 각 db_type의 books와 같은
DB 안에 이 플러그인이 스스로 CREATE TABLE)에 저장한다 - 코어 스키마/마이그레이션 파일은
이 테이블의 존재를 전혀 모른다 (플러그인 개발 가이드 §1 핵심 원칙: "코어는 플러그인 고유
이름을 알지 않는다").

원본 CSV 경로는 플러그인 설정(SOURCE_DB_PATH, 보통 rclone 마운트된 공유 드라이브 경로)으로
관리자가 직접 입력한다. 동기화는 settings.html의 "지금 동기화" 버튼이 도서 컨텍스트 메뉴용
범용 RPC 엔드포인트(/api/media/context-menu/book/plugins/action)를 통해
run_context_menu_action(action_id='sync_now')을 호출하는 방식으로 트리거된다 - 별도의 코어
라우트를 새로 만들지 않고 이미 있는 범용 플러그인 액션 실행 경로를 재사용한다.
"""
import os
import re
import csv
import json
import time
import threading

from flask import session

from plugins.metadata.base import BaseMetadataProvider

TABLE_NAME = "plugin_series_official_relations"

# 매칭 대상이 아닌 db_type(오디오북/영상)은 이 관계 데이터의 도메인(만화/애니 시리즈)과 겹치지 않으므로 제외
SYNC_DB_TYPES = ('general', 'adult')

_NORMALIZE_RE = re.compile(r'[\s　·:!?"\'‘’“”`,.\-~()\[\]{}]+')


def normalize_title(text):
    if not text:
        return ''
    return _NORMALIZE_RE.sub('', str(text)).strip().lower()


class SeriesOfficialRelationsProvider(BaseMetadataProvider):
    """공식 연관작(시퀄/프리퀄/스핀오프 등) 위젯 플러그인."""

    id = "series_official_relations"
    name = "공식 연관작"
    is_searchable = False
    config_schema = [
        {"key": "SOURCE_DB_PATH", "label": "원본 관계 파일 경로 (series_title,related_title,relation_type CSV)", "type": "text", "required": True},
    ]
    detail_sidebar_widget = {"title": "공식 연관작", "order": 10, "sessions": "all"}
    smart_recommend_widget = {"title": "공식 연관작", "order": 10, "sessions": "all"}

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 메타데이터 적용을 지원하지 않습니다."

    # ------------------------------------------------------------------
    # 저장소 (플러그인 전용 테이블 - 코어 스키마와 완전히 분리)
    # ------------------------------------------------------------------

    @staticmethod
    def _engine():
        return os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()

    def _ensure_table(self, db_type):
        gateway = self.get_db_gateway(db_type)
        if self._engine() in ('mariadb', 'mysql'):
            gateway.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    library_id BIGINT NOT NULL,
                    series_name VARCHAR(500) NOT NULL,
                    related_library_id BIGINT NOT NULL,
                    related_series_name VARCHAR(500) NOT NULL,
                    relation_type VARCHAR(30) NOT NULL,
                    sort_order INT DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_psor_lookup (library_id, series_name(255))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
            """)
        else:
            gateway.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_id INTEGER NOT NULL,
                    series_name VARCHAR(500) NOT NULL,
                    related_library_id INTEGER NOT NULL,
                    related_series_name VARCHAR(500) NOT NULL,
                    relation_type VARCHAR(30) NOT NULL,
                    sort_order INTEGER DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            gateway.execute(f"CREATE INDEX IF NOT EXISTS idx_psor_lookup ON {TABLE_NAME}(library_id, series_name)")

    # ------------------------------------------------------------------
    # 위젯 데이터 조회 (detail_sidebar_widget / smart_recommend_widget 공용)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_cover_url(cover_image):
        """books.cover_image의 원본 저장값(파일명/상대경로)을 브라우저가 바로 쓸 수 있는
        /covers/... URL로 정규화한다. author_other_books 샘플 플러그인과 동일한 헬퍼."""
        if not cover_image:
            return None
        clean = str(cover_image).strip()
        if not clean:
            return None
        if clean.startswith("http://") or clean.startswith("https://") or clean.startswith("/"):
            return clean
        clean = clean.lstrip("/\\")
        if clean.lower().startswith("covers/"):
            clean = clean[len("covers/"):].lstrip("/\\")
        return f"/covers/{clean}" if clean else None

    def _get_relations(self, db_type, library_id, series_name):
        gateway = self.get_db_gateway(db_type)
        try:
            rows = gateway.fetch_all(
                f"""
                SELECT related_library_id, related_series_name, relation_type
                FROM {TABLE_NAME}
                WHERE library_id = ? AND series_name = ?
                ORDER BY sort_order ASC, id ASC
                """,
                (library_id, series_name)
            ) or []
        except Exception:
            # 아직 한 번도 동기화하지 않아 테이블이 없는 초기 상태 - 조용히 빈 목록 처리
            return []
        return [dict(r) for r in rows]

    def _get_representative_book(self, db_type, library_id, series_name):
        gateway = self.get_db_gateway(db_type)
        rows = gateway.fetch_all(
            """
            SELECT MIN(id) AS id, MAX(cover_image) AS cover_image, MAX(file_format) AS file_format
            FROM books
            WHERE (is_deleted = 0 OR is_deleted IS NULL) AND library_id = ? AND series_name = ?
            """,
            (library_id, series_name)
        )
        return dict(rows[0]) if rows and rows[0].get('id') is not None else None

    def _build_items(self, db_type, series_name, library_id):
        if not series_name or library_id is None:
            return []
        relations = self._get_relations(db_type, library_id, series_name)
        items = []
        for rel in relations:
            book = self._get_representative_book(db_type, rel['related_library_id'], rel['related_series_name'])
            if not book:
                continue
            items.append({
                'book_id': book['id'],
                'series_name': rel['related_series_name'],
                'library_id': rel['related_library_id'],
                'cover': self._resolve_cover_url(book.get('cover_image')),
                'file_format': book.get('file_format'),
            })
        return items

    def get_detail_sidebar_data(self, db_type, context):
        series_name = (context or {}).get('series_name') or ''
        library_id = (context or {}).get('library_id')
        return {'success': True, 'items': self._build_items(db_type, series_name, library_id)}

    def get_smart_recommend_data(self, db_type, context):
        series_name = (context or {}).get('series_name') or ''
        library_id = (context or {}).get('library_id')
        return {'success': True, 'items': self._build_items(db_type, series_name, library_id)}

    # ------------------------------------------------------------------
    # 동기화 트리거 (settings.js -> 범용 컨텍스트메뉴 액션 RPC 경유)
    # ------------------------------------------------------------------

    def run_context_menu_action(self, db_type, action_id, context):
        if action_id == 'sync_now':
            return self._start_sync(context)
        if action_id == 'sync_status':
            return self._get_sync_status()
        return {'success': False, 'error': f'알 수 없는 액션: {action_id}'}

    @staticmethod
    def _is_admin():
        try:
            return session.get('role') == 'admin'
        except Exception:
            return False

    def _status_key(self):
        return f"PLUGIN_{self.id}_SYNC_STATUS"

    def _get_sync_status(self):
        gateway = self.get_db_gateway('general')
        raw = gateway.get_setting(self._status_key())
        if not raw:
            return {'success': True, 'status': 'never_run'}
        try:
            data = json.loads(raw['value'])
        except Exception:
            data = {'status': 'never_run'}
        return {'success': True, **data}

    def _set_sync_status(self, data):
        gateway = self.get_db_gateway('general')
        gateway.set_setting(self._status_key(), json.dumps(data, ensure_ascii=False))

    def _start_sync(self, context=None):
        if not self._is_admin():
            return {'success': False, 'error': '관리자만 실행할 수 있습니다.'}

        # settings.html 입력창의 현재 값을 우선 사용한다 - "설정 저장" 버튼을 먼저 눌러
        # 영속화해야만 동기화가 되는 게 아니라, 화면에 보이는 값 그대로 바로 실행되게 하기 위함
        # (실제로 이 문제로 한 번 "원본 DB를 찾을 수 없습니다:"(빈 문자열) 오류가 난 적 있음 -
        # 입력만 하고 저장 버튼을 안 눌러 저장된 설정이 비어있던 상태였음). 값이 오면 그대로
        # 설정에도 저장해 다음부터는 다시 입력하지 않아도 되게 한다.
        source_path = ((context or {}).get('source_db_path') or '').strip()
        if source_path:
            self.get_db_gateway('general').set_plugin_config(self.id, {'SOURCE_DB_PATH': source_path})
        else:
            config = self.get_plugin_config('general', default={})
            source_path = (config.get('SOURCE_DB_PATH') or '').strip()

        if not source_path or not os.path.exists(source_path):
            return {'success': False, 'error': f'원본 파일을 찾을 수 없습니다: {source_path or "(경로가 비어 있음)"}'}

        self._set_sync_status({'status': 'running', 'started_at': time.time()})
        threading.Thread(target=self._run_sync_job, args=(source_path,), daemon=True).start()
        return {'success': True, 'message': '공식 연관작 동기화를 시작했습니다.'}

    def _run_sync_job(self, source_path):
        started_at = time.time()
        try:
            results = self._sync(source_path)
            self._set_sync_status({
                'status': 'success', 'started_at': started_at,
                'finished_at': time.time(), 'results': results,
            })
        except Exception as e:
            self._set_sync_status({
                'status': 'error', 'started_at': started_at,
                'finished_at': time.time(), 'error': str(e),
            })

    # ------------------------------------------------------------------
    # 동기화 알고리즘
    #
    # 이 섹션(원본 읽기)만 "당신 데이터 소스에 맞게 갈아끼우는 지점"이다. 아래
    # _read_relation_rows()가 CSV를 파싱해 (series_title, related_title, relation_type)
    # 튜플 리스트를 만들어주기만 하면, 그 다음(_sync_one_db_type - 우리 라이브러리와의
    # 매칭/테이블 저장/위젯 노출)은 전부 그대로 재사용된다. 즉 CSV가 아니라 자기 DB를
    # 직접 쿼리하든, 외부 API를 호출하든 원하는 방식으로 이 메서드 하나만 새로 구현해서
    # 포크하면 된다 - 커뮤니티마다 원본 데이터 형태가 다를 걸 감안해, 우리가 CSV 하나로
    # 스펙을 강제하기보다 이 지점만 명확히 열어두는 쪽을 택했다.
    # ------------------------------------------------------------------

    @staticmethod
    def _read_relation_rows(source_path):
        """[기본 어댑터] `series_title,related_title,relation_type` 3컬럼 CSV(헤더 필수)를
        읽는다. 원본 큐레이터가 자기 쪽 DB의 state/중복 판별을 이미 끝내고 내보낸 결과라고
        가정하므로, 여기서는 별도의 모호성 판별 없이 있는 그대로 읽는다 - 정제는 원본 쪽
        책임, 우리는 그 결과를 우리 라이브러리와 매칭하는 것만 담당한다.

        CSV로 내보내기 번거로운 데이터 소스를 가진 사람은 이 메서드를 자기 방식으로 갈아
        끼우면 된다(예: 자기 DB를 self.get_db_gateway()가 아닌 별도 커넥션으로 직접 쿼리,
        REST API 호출 등) - 반환 형식(튜플 리스트)만 지키면 나머지는 그대로 동작한다."""
        rows = []
        with open(source_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                series_title = (row.get('series_title') or '').strip()
                related_title = (row.get('related_title') or '').strip()
                relation_type = (row.get('relation_type') or '').strip()
                if not series_title or not related_title or not relation_type:
                    continue
                rows.append((series_title, related_title, relation_type))
        return rows

    def _sync(self, source_path):
        relation_rows = self._read_relation_rows(source_path)
        results = {}
        for db_type in SYNC_DB_TYPES:
            results[db_type] = self._sync_one_db_type(db_type, relation_rows)
        return results

    def _get_our_series(self, db_type):
        gateway = self.get_db_gateway(db_type)
        rows = gateway.fetch_all(
            """
            SELECT DISTINCT series_name, library_id
            FROM books
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND series_name IS NOT NULL AND series_name != ''
            """
        ) or []
        return [(dict(r)['series_name'], dict(r)['library_id']) for r in rows]

    def _sync_one_db_type(self, db_type, relation_rows):
        self._ensure_table(db_type)
        gateway = self.get_db_gateway(db_type)

        our_series = self._get_our_series(db_type)
        our_by_normalized = {}
        for series_name, library_id in our_series:
            our_by_normalized.setdefault(normalize_title(series_name), []).append((series_name, library_id))

        rows_to_insert = []
        seen_pairs = set()
        sort_order_by_source = {}
        matched_series = set()

        for series_title, related_title, relation_type in relation_rows:
            source_candidates = our_by_normalized.get(normalize_title(series_title))
            related_candidates = our_by_normalized.get(normalize_title(related_title))
            if not source_candidates or not related_candidates:
                continue

            for src_name, src_lib in source_candidates:
                matched_series.add((src_lib, src_name))
                for rel_name, rel_lib in related_candidates:
                    if src_name == rel_name and src_lib == rel_lib:
                        continue
                    pair_key = (src_lib, src_name, rel_lib, rel_name, relation_type)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    order_key = (src_lib, src_name)
                    sort_order = sort_order_by_source.get(order_key, 0)
                    sort_order_by_source[order_key] = sort_order + 1

                    rows_to_insert.append((
                        src_lib, src_name,
                        rel_lib, rel_name,
                        relation_type, sort_order
                    ))

        gateway.execute(f"DELETE FROM {TABLE_NAME}")
        if rows_to_insert:
            gateway.execute_many(
                f"""
                INSERT INTO {TABLE_NAME}
                    (library_id, series_name, related_library_id, related_series_name, relation_type, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows_to_insert
            )

        return {'matched_series': len(matched_series), 'relations': len(rows_to_insert)}
